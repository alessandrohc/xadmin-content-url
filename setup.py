from setuptools import setup

setup(
	name='xadmin-content-url',
	version='1.6.0',
	packages=[
		'xadmin_content_url',
		'xadmin_content_url.db',
		'xadmin_content_url.migrations',
		'xadmin_content_url.management',
		'xadmin_content_url.management.commands',
		'xadmin_content_url.rest',
		'xadmin_content_url.rest.serializers',
		'xadmin_content_url.forms',
	],
	url='https://github.com/alexsilva/xadmin-content-url',
	include_package_data=True,
	license='MIT',
	author='alex',
	author_email='',
	description=''
)
