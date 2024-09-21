# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------

project = 'SkyShift'
copyright = '2024, SkyShift Team'
author = 'The SkyShift Authors'
release = 'v0.0.0'

# -- General configuration ---------------------------------------------------

def copy_command(cmd, name):
    import click
    return click.Command(
        name=name,
        callback=cmd.callback,
        params=cmd.params,
        help=cmd.help,
        epilog=cmd.epilog,
        short_help=cmd.short_help,
        options_metavar=cmd.options_metavar,
        add_help_option=False,
        no_args_is_help=cmd.no_args_is_help,
        hidden=cmd.hidden,
        deprecated=cmd.deprecated
    )

def rearrange_cli_commands():
    import skyshift.cli.cli as cli_module
    from click import Group
    import click

    new_cli = Group(help="SkyShift CLI")

    object_types = {}

    operation_commands = []
    for name, cmd in cli_module.cli.commands.items():
        if isinstance(cmd, click.Group) and cmd.commands:
            operation_commands.append(name)

    for operation_name in operation_commands:
        operation_group = cli_module.cli.get_command(None, operation_name)
        for cmd_name, cmd_obj in operation_group.commands.items():
            obj_type = cmd_name
            if obj_type not in object_types:
                object_types[obj_type] = {}
            object_types[obj_type][operation_name] = cmd_obj

    for obj_type in sorted(object_types.keys()):
        operations = object_types[obj_type]
        obj_group = Group(name=obj_type, help=f"Commands for {obj_type}")
        for operation_name in sorted(operations.keys()):
            command = operations[operation_name]
            new_command = copy_command(command, name=operation_name)
            obj_group.add_command(new_command, name=operation_name)
        new_cli.add_command(obj_group, name=obj_type)

    for cmd_name, cmd in cli_module.cli.commands.items():
        if cmd_name not in operation_commands:
            new_cli.add_command(cmd, name=cmd_name)

    cli_module.cli = new_cli

rearrange_cli_commands()

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_tabs.tabs',
    'sphinx_click.ext',
]

templates_path = ['_templates']
exclude_patterns = []

main_doc = 'index'

language = 'en'

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'repository_url': 'https://github.com/michaelzhiluo/skyshift',
    'repository_branch': 'main',
    'use_repository_button': True,
    'pygment_light_style': 'tango',
    'pygment_dark_style': 'monokai',
}
html_static_path = ['_static']
html_title = 'SkyShift'

sphinx_tabs_valid_builders = ['linkcheck']
