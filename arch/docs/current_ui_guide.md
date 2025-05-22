# Arch Linux Installer UI Guide: Girly Pop Edition

## 1. Introduction

Welcome to the UI guide for the Arch Linux Installer, "Girly Pop Edition"! This document details the visual elements and functions that create a playful, cute, and stylish command-line interface. The aesthetic aims to be inviting and friendly, reducing the intimidation factor of an installation script while maintaining a clean, modern, and minimal feel.

This guide reflects the **current implementation** found in `arch/modules/ui.py`, drawing inspiration and intent from the `arch/docs/ui_girlypop_plan.md`.

## 2. Color Palette

The UI utilizes a specific set of ANSI escape codes for terminal colors, defined in the `Colors` class within `arch/modules/ui.py`.

| Color Name     | ANSI Code (`ui.py`) | Intended "Girly Pop" Use (from `ui_girlypop_plan.md`)                               |
|----------------|---------------------|------------------------------------------------------------------------------------|
| `PINK`         | `\033[38;5;219m`    | Primary Branding & Headers (Main titles, strong emphasis) - `GP_PINK_PRIMARY`      |
| `PURPLE`       | `\033[38;5;183m`    | (Not explicitly in GP plan, but available)                                         |
| `CYAN`         | `\033[38;5;123m`    | Interactive (Links, interactive choices, info symbols) - `GP_CYAN_INTERACTIVE`     |
| `YELLOW`       | `\033[38;5;228m`    | Status (Warning) - `GP_YELLOW_WARNING`                                             |
| `BLUE`         | `\033[38;5;111m`    | (Not explicitly in GP plan, but available)                                         |
| `ORANGE`       | `\033[38;5;216m`    | (Not explicitly in GP plan, but available; plan suggested `PEACH` for similar uses)|
| `GREEN`        | `\033[38;5;156m`    | Status (Success) - `GP_GREEN_SUCCESS`                                              |
| `RED`          | `\033[38;5;210m`    | Status (Error) - `GP_RED_ERROR`                                                    |
| `MAGENTA`      | `\033[38;5;201m`    | Accent (Special highlights, important interactive elements) - `GP_MAGENTA_ACCENT`  |
| `LIGHT_BLUE`   | `\033[38;5;159m`    | Informational (General info text, spinner messages) - `GP_LIGHT_BLUE_INFO`         |
| `LAVENDER`     | `\033[38;5;147m`    | Primary Branding & Headers (Secondary headers, borders, gentle prompts) - `GP_LAVENDER_PRIMARY` |
| `PEACH`        | `\033[38;5;223m`    | Accent (Highlights, sub-elements, subtle call-outs, invalid input messages) - `GP_PEACH_ACCENT` |
| `MINT`         | `\033[38;5;121m`    | Accent (Positive non-critical info, alternative highlights, info symbols) - `GP_MINT_ACCENT` |
| `PINK_BG`      | `\033[48;5;219m`    | (Background color, not used in current print functions for text styling)           |
| `DARK_BG`      | `\033[48;5;236m`    | (Background color, not used in current print functions for text styling)           |
| `BOLD`         | `\033[1m`           | Text style                                                                         |
| `ITALIC`       | `\033[3m`           | Text style                                                                         |
| `UNDERLINE`    | `\033[4m`           | Text style                                                                         |
| `BLINK`        | `\033[5m`           | Text style                                                                         |
| `RESET`        | `\033[0m`           | Resets all styles and colors                                                       |

*Note: The "GP_" prefixed names refer to the conceptual names in `ui_girlypop_plan.md`.*

## 3. UI Symbols

The following symbols are defined in `arch/modules/ui.py` to provide visual cues:

| Symbol Constant Name    | Visual (from `ui.py`)        | Color (from `ui.py`) | Purpose & "Girly Pop" Intent                                                                 |
|-------------------------|------------------------------|----------------------|----------------------------------------------------------------------------------------------|
| `SUCCESS_SYMBOL`        | `✓`                          | `Colors.GREEN`       | Indicates a successful operation. Plan: `✓` with `GP_GREEN_SUCCESS`.                         |
| `WARNING_SYMBOL`        | `!`                          | `Colors.YELLOW`      | Indicates a warning. Plan: `!` with `GP_YELLOW_WARNING`.                                     |
| `ERROR_SYMBOL`          | `✗`                          | `Colors.RED`         | Indicates an error. Plan: `✗` with `GP_RED_ERROR`.                                           |
| `INFO_SYMBOL`           | `ⓘ`                          | `Colors.MINT`        | Provides informational context. Plan: `ⓘ` with `GP_MINT_ACCENT` (changed from `✧`).          |
| `PROGRESS_SYMBOL`       | `▸`                          | `Colors.LIGHT_BLUE`  | Indicates progress or an action being taken (e.g., running a command). Plan: `▸` with `GP_LIGHT_BLUE_INFO` (changed from `→`). |
| `NOTE_SYMBOL`           | `♡`                          | `Colors.LAVENDER`    | Highlights a note or a piece of advice. Plan: `♡` with `GP_LAVENDER_PRIMARY` (changed from `•`). |
| `STAR_SYMBOL`           | `✨`                         | `Colors.MAGENTA`     | Used for header flair. Plan: `✨` (Sparkles) for main headers. (Changed from `★`).          |
| `CHERRY_BLOSSOM_SYMBOL` | `🌸`                         | `Colors.PINK`        | Decorative symbol. Plan: Main Header Prefix/Suffix.                                          |
| `SPARKLING_HEART_SYMBOL`| `💖`                         | `Colors.PINK`        | Decorative symbol. Plan: Main Header Prefix/Suffix or final "all done" message.              |
| `RIBBON_SYMBOL`         | `୨୧`                         | `Colors.LAVENDER`    | Decorative symbol, used in section headers. Plan: Section Header Prefix/Suffix.              |
| `FLOWER_ICON_SYMBOL`    | `✽`                          | `Colors.PEACH`       | Decorative symbol. Plan: Section Header Prefix/Suffix.                                       |
| `INPUT_PROMPT_SYMBOL`   | `↳`                          | `Colors.CYAN`        | Prefix for user input prompts. Plan: Input Prompt Prefix with `GP_CYAN_INTERACTIVE`.         |

## 4. Styled Printing Functions

These functions handle the styled output to the terminal.

### `print_color(text: str, color: str, bold: bool = False, prefix: Optional[str] = None, italic: bool = False)`

*   **Description:** Prints text in a specified color and style. Can optionally add a prefix.
*   **Parameters:**
    *   `text (str)`: The text to print.
    *   `color (str)`: An ANSI color code from the `Colors` class.
    *   `bold (bool)`: If `True`, makes the text bold. Default: `False`.
    *   `prefix (Optional[str])`: An optional string to prepend to the text (e.g., a symbol). Default: `None`.
    *   `italic (bool)`: If `True`, makes the text italic. Default: `False`.
*   **Example Output (Conceptual):**
    ```
    # print_color("Hello Girly Pop!", Colors.PINK, bold=True, prefix=SPARKLING_HEART_SYMBOL)
    💖 Hello Girly Pop!  (in bold pink)
    ```

### `print_header(title: str)`

*   **Description:** Prints a main section header with the "girly pop aesthetic".
*   **Parameters:**
    *   `title (str)`: The title text for the header.
*   **Implementation:** Uses `print_color(f"✨ {title} ✨", Colors.PINK, bold=True)`.
*   **Visual Output Example:**
    ```
    ✨ Your Main Header Title Here ✨ (in bold pink)

    ```
    *(Note: An extra newline is printed after the header for spacing)*
*   **Alignment with Plan:** Implements Option 1 from the plan (`✨ {title} ✨` with `Colors.PINK`).

### `print_section_header(title: str)`

*   **Description:** Prints a subsection header with a "girly pop" gradient text effect and ribbon symbols.
*   **Parameters:**
    *   `title (str)`: The title text for the subsection header.
*   **Implementation:**
    *   Uses a gradient of `[Colors.PINK, Colors.LAVENDER, Colors.PEACH]` for the title text.
    *   Formats as: `print_color(f"{RIBBON_SYMBOL} {styled_title} {RIBBON_SYMBOL}", Colors.LAVENDER, bold=True)`.
*   **Visual Output Example:**
    ```
    ୨୧ Your Section Title Here ୨୧ (Title text has PINK/LAVENDER/PEACH gradient, ribbons and surrounding text in bold LAVENDER)

    ```
    *(Note: An extra newline is printed after the header for spacing)*
*   **Alignment with Plan:** Implements Option 1 from the plan (`୨୧ {styled_title} ୨୧` with `Colors.LAVENDER`).

### `print_step_info(message: str)`

*   **Description:** Prints an informational message for a step, prefixed with the `INFO_SYMBOL`.
*   **Parameters:**
    *   `message (str)`: The informational message.
*   **Implementation:** Uses `print_color(message, Colors.MINT, prefix=INFO_SYMBOL)`.
*   **Visual Output Example:**
    ```
    ⓘ This is some step information. (Symbol in MINT, text in MINT)
    ```
*   **Alignment with Plan:** Aligns with the plan, using the updated `INFO_SYMBOL` (`ⓘ` in `Colors.MINT`).

### `print_command_info(cmd_str: str)`

*   **Description:** Prints information about a command being executed, prefixed with `PROGRESS_SYMBOL`.
*   **Parameters:**
    *   `cmd_str (str)`: The command string.
*   **Implementation:** Uses `print_color(f"running: {cmd_str}", Colors.LIGHT_BLUE, prefix=PROGRESS_SYMBOL)`.
*   **Visual Output Example:**
    ```
    ▸ running: sudo pacman -Syu (Symbol in LIGHT_BLUE, text in LIGHT_BLUE)
    ```
*   **Alignment with Plan:** Aligns with the plan, using the updated `PROGRESS_SYMBOL` (`▸` in `Colors.LIGHT_BLUE`).

### `print_dry_run_command(cmd_str: str)`

*   **Description:** Prints information about a command that would be executed in dry run mode.
*   **Parameters:**
    *   `cmd_str (str)`: The command string.
*   **Implementation:** Uses `print_color(f"Would execute: {cmd_str}", Colors.PEACH, prefix=f"{Colors.LAVENDER}[DRY RUN]{Colors.RESET}")`.
*   **Visual Output Example:**
    ```
    [DRY RUN] Would execute: mkfs.ext4 /dev/sda1 (Prefix in LAVENDER, text in PEACH)
    ```
*   **Alignment with Plan:** Aligns with the plan, using `Colors.LAVENDER` for the `[DRY RUN]` prefix and `Colors.PEACH` for the command text.

### `print_separator(char: str = "·", color: str = Colors.LAVENDER, length: int = 50)`

*   **Description:** Prints a simple, soft separator line. This function was added based on the plan's suggestions.
*   **Parameters:**
    *   `char (str)`: The character to repeat for the separator. Default: `"·"`.
    *   `color (str)`: The color of the separator line. Default: `Colors.LAVENDER`.
    *   `length (int)`: The length of the separator line. Default: `50`.
*   **Visual Output Example (`print_separator()`):**
    ```
    ·················································· (in LAVENDER)
    ```
*   **Alignment with Plan:** Directly implements the suggested new helper function.

## 5. `Spinner` Class

The `Spinner` class provides a simple CLI animation for long-running operations.

*   **`__init__(self, message: str = "Processing...", delay: float = 0.1, spinner_chars: Optional[TypingList[str]] = None)`**
    *   **Description:** Initializes the spinner.
    *   **Parameters:**
        *   `message (str)`: The message to display next to the spinner. Default: `"Processing..."`.
        *   `delay (float)`: The delay in seconds between spinner frames. Default: `0.1`.
        *   `spinner_chars (Optional[TypingList[str]])`: A list of characters for the spinner animation.
            *   Default (Girly Pop): `['✿', '❀', '✾', '❁', '✽']` (Flower Spinner)
*   **Visual Appearance & Styling:**
    *   The spinner character (e.g., `✿`) is printed in `Colors.PINK`.
    *   The message (e.g., "Processing...") is printed in `Colors.LIGHT_BLUE`.
    *   Example: `✿ Processing...` (with `✿` in PINK, "Processing..." in LIGHT_BLUE, and `✿` cycling through `❀`, `✾`, `❁`, `✽`)
*   **Methods:**
    *   `start(self)`: Starts the spinner animation in a separate thread. Only runs if in a TTY.
    *   `stop(self)`: Stops the spinner animation and clears the spinner line.
*   **Alignment with Plan:**
    *   Implements the "Flower Spinner" (`['✿', '❀', '✾', '❁', '✽']`) as default.
    *   Colors the spinner character with `Colors.PINK` (plan suggested `GP_PINK_PRIMARY` or `GP_MAGENTA_ACCENT`) and the message with `Colors.LIGHT_BLUE` (plan suggested `GP_LIGHT_BLUE_INFO`).

## 6. User Input Functions

These functions handle prompting the user for input.

### `prompt_yes_no(question: str, default_yes: bool = False) -> bool`

*   **Description:** Prompts the user for a yes/no answer with a "girly pop" aesthetic.
*   **Parameters:**
    *   `question (str)`: The question to ask the user.
    *   `default_yes (bool)`: If `True`, 'Y' is the default and capitalized. If `False`, 'n' is the default and capitalized. Default: `False`.
*   **Styling & Interaction:**
    *   Question text is printed in `Colors.LAVENDER`.
    *   The `[Y/n]` suffix highlights the default choice:
        *   If `default_yes` is `True`: `[<MAGENTA>Y</MAGENTA>/<LAVENDER>n</LAVENDER>]`
        *   If `default_yes` is `False`: `[<LAVENDER>y</LAVENDER>/<MAGENTA>N</MAGENTA>]`
    *   User input is case-insensitive ('y', 'yes', 'n', 'no').
    *   Empty input defaults to the `default_yes` value.
    *   Invalid input message ("Invalid input. Please enter 'y' or 'n'.") is printed in `Colors.PEACH` prefixed with `WARNING_SYMBOL`.
*   **Visual Output Example (`prompt_yes_no("Install cute themes?", default_yes=True)`):**
    ```
    Install cute themes? [Y/n]:  (Question in LAVENDER, Y in MAGENTA, /n in LAVENDER)
    ```
*   **Alignment with Plan:**
    *   Question color `Colors.LAVENDER` matches plan.
    *   Suffix styling with `Colors.MAGENTA` for the active choice and `Colors.LAVENDER` for the inactive choice matches the plan.
    *   Invalid input message color changed to `Colors.PEACH` as per plan (from `Colors.ORANGE`).

### `prompt_input(question: str, default: Optional[str] = None, validator: Optional[Callable[[str], bool]] = None, sensitive: bool = False) -> str`

*   **Description:** Prompts the user for text input, with optional default value and validation.
*   **Parameters:**
    *   `question (str)`: The question to ask the user.
    *   `default (Optional[str])`: An optional default value if the user enters nothing.
    *   `validator (Optional[Callable[[str], bool]])`: An optional function to validate the input.
    *   `sensitive (bool)`: If `True`, attempts basic sensitive input (though `getpass` is usually better). Default: `False`.
*   **Styling & Interaction:**
    *   The prompt is prefixed with `INPUT_PROMPT_SYMBOL` (`↳` in `Colors.CYAN`).
    *   The question text is printed in `Colors.MINT`.
    *   If a `default` value is provided (and not `sensitive`), it's shown as `(default: <PEACH>value</PEACH>)` appended to the question (default value in `Colors.PEACH`).
    *   Empty input returns the `default` value if provided.
    *   If input is empty and no default is set, an error message ("Input cannot be empty.") is printed in `Colors.PEACH` prefixed with `WARNING_SYMBOL`.
    *   Messages for `KeyboardInterrupt` or `EOFError` are also styled with `Colors.PEACH` and `WARNING_SYMBOL`.
*   **Visual Output Example (`prompt_input("Enter your favorite color", default="Pink")`):**
    ```
    ↳ Enter your favorite color (default: Pink):  (↳ in CYAN, question in MINT, "(default: Pink)" with "Pink" in PEACH)
    ```
*   **Alignment with Plan:**
    *   Question color `Colors.MINT` matches plan.
    *   Default value highlight color is `Colors.PEACH` (plan allowed `Colors.CYAN` or `Colors.PEACH`; implementation chose `PEACH`).
    *   Adds `INPUT_PROMPT_SYMBOL` (`↳`) as per plan.
    *   Empty input message color changed to `Colors.PEACH` as per plan (from `Colors.ORANGE`).

## 7. UI Flow Overview (Mermaid Diagram)

This diagram provides a conceptual overview of how the UI elements are typically used within the installer script.

```mermaid
graph TD
    A[Script Action] --> B{UI Element Type};
    B -- Main Title --> C([`print_header`]):::funcStyle;
    B -- Section Title --> D([`print_section_header`]):::funcStyle;
    B -- Informational Message --> E([`print_step_info`]):::funcStyle;
    B -- Command Execution --> F([`print_command_info`]):::funcStyle;
    B -- Dry Run Command --> F_DRY([`print_dry_run_command`]):::funcStyle;
    B -- Visual Separator --> SEP([`print_separator`]):::funcStyle;
    B -- User Input Needed --> G{Prompt Type};
    G -- Yes/No Question --> H([`prompt_yes_no`]):::funcStyle;
    G -- General Text Input --> I([`prompt_input`]):::funcStyle;
    B -- Long Operation --> J([`Spinner`]):::classStyle;

    subgraph "Visual Output Examples (Conceptual)"
        C_Out["✨ Main Title ✨"]:::outputStyle
        D_Out["୨୧ Styled Section Title ୨୧"]:::outputStyle
        E_Out["ⓘ Step Information"]:::outputStyle
        F_Out["▸ running: command"]:::outputStyle
        F_DRY_Out["<LAVENDER>[DRY RUN]</LAVENDER> Would execute: command"]:::outputStyle
        SEP_Out["<LAVENDER>··························</LAVENDER>"]:::outputStyle
        H_Out["<LAVENDER>Question</LAVENDER> [<MAGENTA>Y</MAGENTA>/<LAVENDER>n</LAVENDER>]: ":::outputStyle
        I_Out["<CYAN>↳</CYAN> <MINT>Question</MINT> (default: <PEACH>value</PEACH>): ":::outputStyle
        J_Out["<PINK>✿</PINK> <LIGHT_BLUE>Processing...</LIGHT_BLUE>"]:::outputStyle
    end

    C --> C_Out;
    D --> D_Out;
    E --> E_Out;
    F --> F_Out;
    F_DRY --> F_DRY_Out;
    SEP --> SEP_Out;
    H --> H_Out;
    I --> I_Out;
    J --> J_Out;

    classDef funcStyle fill:#E6E6FA,stroke:#9370DB,stroke-width:2px,color:#333;
    classDef classStyle fill:#FFDAB9,stroke:#FFA07A,stroke-width:2px,color:#333;
    classDef outputStyle fill:#FFF0F5,stroke:#DB7093,stroke-width:1px,color:#555,font-style:italic;