import sublime
import sublime_plugin
import subprocess
import os
import threading
import json


class IdeHelperOnProjectOpen(sublime_plugin.EventListener):
    """Detect Laravel projects and manage ide-helper on project open."""

    _checked_roots = set()

    def on_activated_async(self, view):
        window = view.window()
        if not window:
            return

        folders = window.folders()
        if not folders:
            return

        root = folders[0]
        if root in self._checked_roots:
            return

        artisan = os.path.join(root, "artisan")
        if not os.path.isfile(artisan):
            return

        self._checked_roots.add(root)
        threading.Thread(target=self._check, args=(root, window), daemon=True).start()

    @staticmethod
    def _check(root, window):
        composer_json = os.path.join(root, "composer.json")
        if not os.path.isfile(composer_json):
            return

        try:
            with open(composer_json, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        require_dev = data.get("require-dev", {})
        has_package = "barryvdh/laravel-ide-helper" in require_dev

        if not has_package:
            sublime.set_timeout(
                lambda: _prompt_install(window, root), 0
            )
            return

        # Package is installed — run ide-helper generation in background
        sublime.status_message("IDE Helper: refreshing…")
        subprocess.run(
            ["composer", "run", "post-update-cmd"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        sublime.status_message("IDE Helper: ready")


def _prompt_install(window, root):
    items = [
        "Install barryvdh/laravel-ide-helper and configure composer.json",
        "Skip for this session",
    ]

    def on_select(index):
        if index == 0:
            threading.Thread(
                target=_install_and_configure, args=(root,), daemon=True
            ).start()

    window.show_quick_panel(items, on_select)


def _install_and_configure(root):
    sublime.status_message("IDE Helper: installing…")

    result = subprocess.run(
        ["composer", "require", "--dev", "barryvdh/laravel-ide-helper"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sublime.status_message("IDE Helper: composer require failed")
        return

    # Add ide-helper commands to post-update-cmd in composer.json
    composer_json = os.path.join(root, "composer.json")
    try:
        with open(composer_json, "r") as f:
            data = json.load(f)

        scripts = data.setdefault("scripts", {})
        post_update = scripts.setdefault("post-update-cmd", [])

        ide_commands = [
            "@php artisan ide-helper:generate",
            "@php artisan ide-helper:models -N",
            "@php -d memory_limit=512M artisan ide-helper:meta",
        ]
        for cmd in ide_commands:
            if cmd not in post_update:
                post_update.append(cmd)

        with open(composer_json, "w") as f:
            json.dump(data, f, indent=4)
            f.write("\n")
    except (json.JSONDecodeError, OSError):
        sublime.status_message("IDE Helper: failed to update composer.json")
        return

    # Add generated files to .gitignore
    gitignore = os.path.join(root, ".gitignore")
    ignore_entries = ["_ide_helper.php", "_ide_helper_models.php", ".phpstorm.meta.php"]
    try:
        existing = ""
        if os.path.isfile(gitignore):
            with open(gitignore, "r") as f:
                existing = f.read()

        to_add = [e for e in ignore_entries if e not in existing]
        if to_add:
            with open(gitignore, "a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(to_add) + "\n")
    except OSError:
        pass

    # Generate the helper files
    sublime.status_message("IDE Helper: generating files…")
    subprocess.run(
        ["composer", "run", "post-update-cmd"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sublime.status_message("IDE Helper: installed and ready")
