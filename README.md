# Laravel IDE Helper for Sublime Text

A Sublime Text plugin that automatically manages [barryvdh/laravel-ide-helper](https://github.com/barryvdh/laravel-ide-helper) for your Laravel projects.

## What it does

When you open a Laravel project, this plugin:

1. **Detects Laravel** by looking for an `artisan` file in the project root
2. **If ide-helper is installed** — runs `composer run post-update-cmd` to regenerate helper files
3. **If ide-helper is not installed** — prompts you to install it via a quick panel

When you choose to install, the plugin:

- Runs `composer require --dev barryvdh/laravel-ide-helper`
- Adds generation commands to `composer.json` `post-update-cmd` scripts:
  - `@php artisan ide-helper:generate`
  - `@php artisan ide-helper:models -N`
  - `@php -d memory_limit=512M artisan ide-helper:meta`
- Adds generated files (`_ide_helper.php`, `_ide_helper_models.php`, `.phpstorm.meta.php`) to `.gitignore`
- Runs the generation immediately

## Installation

Clone or symlink this repository into your Sublime Text `Packages` directory:

```
# macOS
cd ~/Library/Application\ Support/Sublime\ Text/Packages
git clone <repo-url> LaravelIdeHelper

# Linux
cd ~/.config/sublime-text/Packages
git clone <repo-url> LaravelIdeHelper
```

## Requirements

- PHP and Composer available on your `PATH`
- A Laravel project with a `composer.json`

## How it works

The plugin uses an `EventListener` that fires on view activation. It checks each project root once per session, running all operations in background threads to keep the editor responsive. Status messages appear in the Sublime Text status bar.
