# Plan to Create Consolidated UI Documentation (`arch/docs/current_ui_guide.md`)

This document outlines the plan to create a new, consolidated UI documentation file, `arch/docs/current_ui_guide.md`, reflecting the "girly pop aesthetic" as implemented in `arch/modules/ui.py` and based on the plan in `arch/docs/ui_girlypop_plan.md`.

## 1. Understand the "Girly Pop Aesthetic"
*   Review the core concepts, keywords, and goals outlined in `arch/docs/ui_girlypop_plan.md` to ensure the documentation narrative aligns with the intended feel.

## 2. Document the `Colors` Class
*   List each color defined in the `Colors` class in `arch/modules/ui.py`.
*   For each color, describe its intended use and meaning within the "girly pop aesthetic" by cross-referencing the definitions in the plan (`arch/docs/ui_girlypop_plan.md`).

## 3. Document UI Symbols
*   Identify all symbols defined in `arch/modules/ui.py` (e.g., `SUCCESS_SYMBOL`, `INFO_SYMBOL`, `RIBBON_SYMBOL`, etc.).
*   For each symbol:
    *   Show its visual appearance (the character itself and its applied color).
    *   Explain its purpose and context of use, based on both the implementation and the plan's suggestions (`arch/docs/ui_girlypop_plan.md`).

## 4. Document Styled Printing Functions
*   For each of the following functions in `arch/modules/ui.py`:
    *   `print_color`
    *   `print_header`
    *   `print_section_header`
    *   `print_step_info`
    *   `print_command_info`
    *   `print_dry_run_command`
    *   `print_separator` (newly added based on the plan)
*   Detail:
    *   Its parameters and their types.
    *   A clear description of what the function does.
    *   An example of its visual output, accurately reflecting the colors, symbols, and formatting as implemented in `arch/modules/ui.py`.
    *   Briefly note if the implementation aligns with or deviates from the suggestions in `arch/docs/ui_girlypop_plan.md` for that function.

## 5. Document the `Spinner` Class
*   Describe the `Spinner` class from `arch/modules/ui.py`.
*   Detail its visual appearance:
    *   The sequence of spinner characters used (`['✿', '❀', '✾', '❁', '✽']`).
    *   The color of the spinner character (e.g., `Colors.PINK`).
    *   The color of the accompanying message (e.g., `Colors.LIGHT_BLUE`).
*   Explain its usage, covering:
    *   Parameters for `__init__` (message, delay, spinner_chars).
    *   How to use the `start()` and `stop()` methods.
*   Reference the plan's specifications for the spinner (`arch/docs/ui_girlypop_plan.md`).

## 6. Document User Input Functions
*   For `prompt_yes_no` and `prompt_input` in `arch/modules/ui.py`:
*   Describe:
    *   Their specific styling (colors for question text, default value highlights, prompt symbols like `↳`).
    *   The interaction flow (how they present questions, handle user input, display default options, and manage invalid input messages).
    *   Ensure the documentation reflects the actual colors (e.g., `Colors.PEACH` for invalid input messages) and formatting used in the code.
*   Compare with the plan's proposals (`arch/docs/ui_girlypop_plan.md`).

## 7. Structure and Create the New Documentation File
*   Create a new Markdown file named `arch/docs/current_ui_guide.md`.
*   Organize the content with clear headings for:
    *   Introduction (briefly explaining the "girly pop aesthetic" and the purpose of the guide).
    *   Color Palette.
    *   UI Symbols.
    *   Styled Printing Functions (with sub-sections for each function).
    *   Spinner.
    *   User Input Functions (with sub-sections for each).
*   Use Markdown effectively (code blocks for examples, lists, bolding for emphasis) to ensure the document is readable and easy to navigate.
*   **Crucially, all information must accurately reflect the *current implementation* in `arch/modules/ui.py`.**

## 8. Include a Mermaid Diagram (Optional Enhancement)
*   To visually summarize the UI components and their typical usage, consider including an updated Mermaid diagram. This diagram would show the main UI functions and how they contribute to the overall user experience.

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

    subgraph "Visual Output Examples"
        C_Out["✨ Main Title ✨"]:::outputStyle
        D_Out["୨୧ Styled Section Title ୨୧"]:::outputStyle
        E_Out["ⓘ Step Information"]:::outputStyle
        F_Out["▸ running: command"]:::outputStyle
        F_DRY_Out["<lavender_color>[DRY RUN]</lavender_color> Would execute: command"]:::outputStyle
        SEP_Out["<lavender_color>··························</lavender_color>"]:::outputStyle
        H_Out["<lavender_color>Question</lavender_color> [<magenta_color>Y</magenta_color>/<lavender_color>n</lavender_color>]: ":::outputStyle
        I_Out["<cyan_color>↳</cyan_color> <mint_color>Question</mint_color> (default: <peach_color>value</peach_color>): ":::outputStyle
        J_Out["<pink_color>✿</pink_color> <light_blue_color>Processing...</light_blue_color>"]:::outputStyle
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