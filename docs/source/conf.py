# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Skyshift'
copyright = '2024, Skyshift Team'
author = 'The Skyshift Authors'
release = 'v0.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_tabs.tabs',
]

templates_path = ['_templates']
exclude_patterns = []

main_doc = 'index'

language = 'en'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'repository_url': 'https://github.com/michaelzhiluo/skyflow',
    'repository_branch': 'main',
    'use_repository_button': True,
    'pygment_light_style': 'tango',
    'pygment_dark_style': 'monokai',
}
html_static_path = ['_static']
html_title = 'Skyshift'

sphinx_tabs_valid_builders = ['linkcheck']