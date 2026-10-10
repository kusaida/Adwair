# Adwair

A refined icon theme blending the polished look of WhiteSur with the clean, native feel of Adwaita.

![Adwair Preview](preview/preview.png)

## Installation

### Automatic installation

Clone the repository and run the installer:

```bash
git clone https://github.com/kusaida/Adwair.git
cd Adwair
chmod +x install.sh
./install.sh
```

The theme will be installed to:

```text
~/.local/share/icons/Adwair
```

After installation, select **Adwair** as your icon theme.

### Manual installation

If you prefer not to use the installer, copy the contents of `src` directly into your local icon theme directory:

```bash
mkdir -p ~/.local/share/icons/Adwair
cp -r src/. ~/.local/share/icons/Adwair/
```

Then select **Adwair** as your icon theme.

### Installation options

The installer supports colored folder variants and custom installation names.

|  OPTIONS:                  |                                                                              |
|:---------------------------|:-----------------------------------------------------------------------------|
| -c, --color [COLOR]        | Specify color variant [blue/green/orange/pink/purple/red/slate/teal/yellow] (Default: blue) |
| -a, --apps                 | Install colored app icons (requires -c)                                      |
| -d, --dark                 | Install dark icons (cannot be combined with -a)                              |
| -n, --name NAME            | Specify theme name (Default: Adwair)                                         |
| -p, --path PATH            | Specify installation directory (Default: $HOME/.local/share/icons)           |
| -f, --folder-icons         | Assign folder icons by name after install (requires gio)                     |
| -r, --remove, -u, --uninstall | Uninstall (remove) the theme                                              |
| -F, --folder-name          | With -r/-u: also reset folder icons set by -f                                |
| -h, --help                 | Show this help                                                               |

#### Colored folders

```bash
./install.sh -c COLOR
```

![Adwair folder variants](preview/folders.png)

#### Colored folders and app icons

```bash
./install.sh -c COLOR -a
```

![Adwair colored app icons](preview/apps-recolor-preview.png)

## Cursor theme

A modernized Adwaita cursor theme with HiDPI support. It is already included and installed with the icon theme, just select **Adwair** as the cursor theme in **Refine** or **GNOME Tweaks**, the same way as the icon theme.

![Adwair cursor preview](preview/preview_cursor.png)

<details>
<summary>Animated cursors</summary>

![Adwair animated cursors](preview/preview_cursor.gif)

</details>

## Custom folders

The `-f` / `--folder-icons` option runs the custom folder icon generator after installation.

The generator scans directories on the system and automatically assigns matching folder icons based on their names.

For example:
- `github` → `folder-github`
- `Downloads` → `folder-downloads`
- `Pictures` → `folder-pictures`

This allows folders to automatically receive themed icons without manually changing them one by one.

```bash
# Teal folders with a custom theme name and run the folder generator
./install.sh -c t -n MyIcons -f
```

## Credits

Adwair is a derivative work based on and incorporating modified artwork from the following projects:

- [WhiteSur Icon Theme](https://github.com/vinceliuice/WhiteSur-icon-theme) by vinceliuice — GPL-3.0
- [Hatter](https://github.com/Mibea/Hatter) by Mibea — GPL-3.0
- [MoreWaita](https://github.com/somepaulo/MoreWaita) by somepaulo — GPL-3.0
- [Adwaita Icon Theme](https://gitlab.gnome.org/GNOME/adwaita-icon-theme) by the [GNOME Project](https://www.gnome.org) — used under LGPL-3.0

### Modifications

- **App icons:** based on WhiteSur, with extensive modifications and additions.
- **Some app icons:** based on Hatter and adapted to the WhiteSur style.
- **Symbolic icons:** from Adwaita and MoreWaita.
- **Cursors:** modernized Adwaita cursor theme with HiDPI support.
- **Folder icons:** modified Adwaita artwork combined with Adwaita symbolic icons.
- Several app icons are original artwork.

## License

Adwair is licensed under the [GPL-3.0](LICENSE).
