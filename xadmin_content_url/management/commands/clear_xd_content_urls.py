from django.core.management.base import BaseCommand
from xadmin_content_url.models import XdContentUrl


class Command(BaseCommand):
    help = """Removes URL links (XdContentUrl) that point to deleted objects."""

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting cleanup of orphaned URL links..."))

        links_to_delete = []

        # We use iterator() for memory efficiency on large tables
        # and select_related() to avoid a query per loop to fetch the ContentType.
        total_links = 0
        for link in XdContentUrl.objects.select_related('content_type').iterator():
            total_links += 1
            # The 'content_object' property does the magic.
            # It returns None if the related object no longer exists,
            # either because the row was deleted or even the entire table is gone.
            if link.content_object is None:
                links_to_delete.append(link.pk)
                self.stdout.write(
                    self.style.WARNING(
                        f"  -> Marked for deletion: Orphaned link ID {link.pk} "
                        f"(pointed to '{link.content_type}' with object_id: {link.object_id})"
                    )
                )

        if not links_to_delete:
            self.stdout.write(self.style.SUCCESS(f"No orphaned links found out of {total_links} total links. The database is clean!"))
            return

        orphaned_count = len(links_to_delete)
        self.stdout.write(self.style.NOTICE(f"\nFound {orphaned_count} orphaned links out of {total_links} total."))

        # Delete all orphaned links at once for better performance.
        # The delete() here will still trigger CASCADE to XdUrl, which is the
        # correct behavior for a truly orphaned link.
        queryset = XdContentUrl.objects.filter(pk__in=links_to_delete)
        queryset.delete()

        self.stdout.write(self.style.SUCCESS(f"Cleanup complete. {orphaned_count} orphaned links were removed."))
