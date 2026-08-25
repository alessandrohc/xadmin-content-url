// Wraps the code in an IIFE to create a safe scope and avoid conflicts with the '$' alias.
(function ($) {
    'use strict';

    // Use of ES6 classes for a clearer and more modern structure.
    class ContentUrl {
        constructor($el, options) {
            this.$el = $el;
            this.options = options;
            this.modal = null;
            this.$dt = null; // DataTable instance

            this.icons = {
                loading: "fa fa-spin fa-spinner mr-2",
                error: "fa fa-exclamation-triangle mr-2",
            };

            // Use an arrow function to maintain the 'this' context without needing $.proxy.
            this.$el.on('click', () => this.init());
        }

        // 'init' method using .done() and .fail() instead of async/await.
        init() {
            const modal = this.getModal();
            this.getBtnInsert().prop("disabled", true);
            modal.loading();
            modal.show();

            $.ajax({ url: this.$el.data('url') })
                .done(html => {
                    // Request success
                    this.reload(html);
                })
                .fail(error => {
                    // Request failure
                    console.error("Failed to load modal content:", error);
                    const forName = this.$el.data("for_name");
                    // Arrow function maintains 'this'
                    const retryAction = () => this.init();
                    modal.fail(modal.retry_action(forName, retryAction));
                });
        }

        /* Initializes the modal and prepares for a new table load */
        reload(html) {
            const modal = this.getModal();
            modal.set_content(html);

            const $form = modal.$modal.find("form.xdm_ct_url_form");
            $form.find("button.btn-content-select").on('click', () => this.ajaxTable());

            if (this.$dt) {
                this.$dt.destroy();
                this.$dt = null;
            }
        }

        // "Getter" methods for caching jQuery elements.
        getBtnInsert() {
            if (!this.$btnInsert) {
                this.$btnInsert = this.getModal().find("button.xd_ct_insert");
                this.$btnInsert.attr("data-dismiss", (_, value) => value !== undefined ? value : 'modal');
            }
            return this.$btnInsert;
        }

        getModalFooter() {
            if (!this.$modalFooter) {
                this.$modalFooter = this.getModal().find(".modal-footer");
            }
            return this.$modalFooter;
        }

        getSelection() {
            return this.getModal().find("form.xdm_ct_url_form #id_xdm-content").val();
        }

        /* Builds the URL for the initial form */
        getRestUrl(modelLabel) {
            if (window.Urls) {
                const urlName = `xadmin:${modelLabel.replace(".", "_")}_rest`;
                return Urls[urlName]();
            }
            return `${xadmin.path_prefix}${modelLabel.replace(".", "/")}/rest`;
        }
        
        /**
         * Returns the internal and display values associated with this instance.
         * @returns {{internalValue: string, displayValue: string}|null}
         */
        getValue() {
            const forName = this.$el.data('for_name');
            if (!forName) {
                console.error('ContentUrl: "data-for_name" attribute not found.');
                return null;
            }
            const $input = this.$el.closest('form').find(`input[name='${forName}']`);
            const $selInput = this.$el.closest('form').find(`input[name='sel_${forName}']`);

            return {
                internalValue: $input.val(),
                displayValue: $selInput.val()
            };
        }

        /**
         * Sets the internal and display values.
         * Triggers the 'change' event on the main input if the value is changed.
         * @param {{internalValue: string, displayValue: string}} data - The object with the values to be set.
         * @returns {boolean} - Returns true if the value was changed, false otherwise.
         */
        setValue(data) {
            if (!data || typeof data.internalValue === 'undefined' || typeof data.displayValue === 'undefined') {
                console.error('ContentUrl: setValue() requires an object with internalValue and displayValue properties.');
                return false;
            }

            const forName = this.$el.data('for_name');
            if (!forName) {
                console.error('ContentUrl: "data-for_name" attribute not found.');
                return false;
            }
            const $input = this.$el.closest('form').find(`input[name='${forName}']`);
            const $selInput = this.$el.closest('form').find(`input[name='sel_${forName}']`);

            const oldInternalValue = $input.val();
            
            // Compare the old value with the new one to detect the change.
            if (oldInternalValue !== data.internalValue) {
                $input.val(data.internalValue);
                $selInput.val(data.displayValue);
                
                // Triggers the default jQuery 'change' event on the main input.
                $input.trigger('change');
                
                return true; // Reports that the change occurred.
            }

            return false; // Reports that no change was necessary.
        }

        ajaxTable() {
            const $form = this.getModal().find("form.xdm_ct_url_form");
            const $icon = $form.find("button.btn-content-select i");
            const $sel = $form.find("#id_xdm-content");
            const url = this.getRestUrl($sel.val());
            
            $form.find(".xdm_ct_url_table_wrapper").removeClass('d-none');
            const $table = $form.find("table.xdm_ct_url_table").removeClass('d-none');

            const params = { plugin: "xd_ct_url", 'format': 'datatables' };

            if (!this.$dt) {
                this.$dt = $table.DataTable({
                    dom: "<'row align-items-center'<'col-sm-12 col-md-6 p-1'l><'col-sm-12 col-md-6 p-1'f>>" +
                         "<'row'<'col-sm-12'tr>>" +
                         "<'row mt-3'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
                    ajax: {
                        url: url,
                        data: params,
                        error: (jqXHR, textStatus, errorThrown) => {
                            const data = (jqXHR.responseJSON || {}).data;
                            const text = textStatus || '';
                            $icon.removeClass(this.icons.loading).addClass(this.icons.error);
                            $icon.attr("title", data ? data.detail || text : text);
                        },
                    },
                    select: {
                        info: false,
                        style: 'single'
                    },
                    processing: true,
                    language: {
                        url: $table.data('language-url'),
                    },
                });

                this.$dt.on('preXhr', () => {
                    $icon.addClass(this.icons.loading).removeAttr("title");
                });
                this.$dt.on('draw', () => {
                    $icon.removeClass(this.icons.loading).removeClass(this.icons.error);
                });
                this.$dt.on('select', (e, dt, type) => this.dtRowSelected(e, dt, type));
                this.$dt.on('deselect', (e, dt, type) => this.dtRowDeselected(e, dt, type));
            } else {
                this.$dt.ajax.url(url).load();
            }
        }

        dtRowSelected(e, dt, type) {
            if (type === 'row') {
                this.getBtnInsert().prop("disabled", false);
            }
        }

        dtRowDeselected(e, dt, type) {
            if (type === 'row') {
                this.getBtnInsert().prop("disabled", true);
            }
        }

        /**
         * Collects data from the selected DataTable row and uses the
         * setValue method to populate the fields.
         */
        insert() {
            const selectedData = this.$dt.rows({ selected: true }).data();
            const modelLabel = this.getSelection();
            
            const dataToSet = {
                internalValue: `${modelLabel.replace(".", ":")}:${selectedData.pluck('id')[0]}`,
                displayValue: selectedData.pluck('url')[0]
            };

            this.setValue(dataToSet);
        }

        getModal() {
            if (!this.modal) {
                this.modal = xadmin.bs_modal({
                    header: { tag: 'h5', title: gettext("Content URL") },
                    modal: { size: 'modal-lg', id: "xd_content_url_modal" },
                    cancel_button: { 'class': 'd-none' },
                    confirm_button: {
                        'class': 'sticky-bottom xd_ct_insert',
                        'text': gettext("Insert selected")
                    }
                });

                this.getModalFooter().addClass('sticky-bottom');
                this.modal.appendTo('body');
                
                const $btn = this.getBtnInsert().prop("disabled", true);
                $btn.on('click', () => this.insert());
            }
            return this.modal;
        }
    }

    // jQuery plugin creation.
    $.fn.select_ct_url = function (options) {
        return this.each(function () {
            const $el = $(this);
            $el.addClass('xd_sel_url_initialized'); 
            if (!$el.data('xd_content_url')) {
                $el.data('xd_content_url', new ContentUrl($el, options));
            }
        });
    };

    // Auto-initialization of the plugin on elements with the correct class when the DOM is ready.
    $(function () {
        $(".xd_content_url_sel_btn").select_ct_url();
    });

    // Suporte a inlines dinâmicos (ex: BannerInline em BannerGallery)
    if ($.fn.exform) {
        $.fn.exform.renders.push(function(form) {
            form.on("formset:added", function(evt, form_row) {
                $(form_row).find(".xd_content_url_sel_btn").select_ct_url();
            });
        });
    }

})(jQuery);
