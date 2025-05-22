# UI Overhaul Plan: "Girly Pop Aesthetic" for Arch Linux Installer CLI

**1. Defining the "Girly Pop Aesthetic" for CLI**

*   **Core Idea:** The aesthetic aims to be playful, cute, and stylish, while maintaining a clean, modern, and minimal feel suitable for a CLI. It should be inviting and friendly, reducing the intimidation factor of an installation script without becoming childish or overly complex.
*   **Keywords:** Soft, elegant, whimsical, charming, clean.
*   **Inspiration:** Think of a refined, digital version of "pastel kawaii" or "soft glam" – subtle, stylish, and functional.
*   **Goal:** To make the installation process visually pleasing and distinct, enhancing user experience while ensuring clarity and usability.

**2. Proposed Color Palette**

This palette leverages existing colors in `arch/modules/ui.py` but applies them with a specific "girly pop" intent.

*   **Primary Branding & Headers:**
    *   `GP_PINK_PRIMARY`: `Colors.PINK` (`\033[38;5;219m`) - For main titles, strong emphasis.
    *   `GP_LAVENDER_PRIMARY`: `Colors.LAVENDER` (`\033[38;5;147m`) - For secondary headers, borders, gentle prompts.
*   **Accent Colors:**
    *   `GP_PEACH_ACCENT`: `Colors.PEACH` (`\033[38;5;223m`) - For highlights, sub-elements, subtle call-outs.
    *   `GP_MINT_ACCENT`: `Colors.MINT` (`\033[38;5;121m`) - For positive non-critical info, alternative highlights.
    *   `GP_MAGENTA_ACCENT`: `Colors.MAGENTA` (`\033[38;5;201m`) - For special highlights, important interactive elements.
*   **Informational & Interactive:**
    *   `GP_CYAN_INTERACTIVE`: `Colors.CYAN` (`\033[38;5;123m`) - For links, interactive choices, info symbols.
    *   `GP_LIGHT_BLUE_INFO`: `Colors.LIGHT_BLUE` (`\033[38;5;159m`) - For general informational text, spinner messages.
*   **Status Colors (Standard, but used thoughtfully):**
    *   `GP_GREEN_SUCCESS`: `Colors.GREEN` (`\033[38;5;156m`)
    *   `GP_YELLOW_WARNING`: `Colors.YELLOW` (`\033[38;5;228m`)
    *   `GP_RED_ERROR`: `Colors.RED` (`\033[38;5;210m`)
*   **Text & Background:**
    *   `GP_TEXT_PRIMARY`: Default terminal white/light gray for maximum readability.
    *   `GP_BACKGROUND`: Default terminal dark background. We will not alter this.

**3. Proposed Symbols & Icons**

Symbols should be cute, simple, and widely supported by terminal fonts.

*   **Headers/Sections:**
    *   Main Header Prefix/Suffix: `✨` (Sparkles), `🌸` (Cherry Blossom), `💖` (Sparkling Heart)
    *   Section Header Prefix/Suffix: `୨୧` (Ribbon), `✽` (Flower icon), `▸` (Soft arrow)
*   **Status Indicators (modifying existing constants in `arch/modules/ui.py`):**
    *   `SUCCESS_SYMBOL`: Keep `✓` (colored with `GP_GREEN_SUCCESS`). For a very final "all done" message, perhaps `💖` (colored with `GP_PINK_PRIMARY`).
    *   `WARNING_SYMBOL`: Keep `!` (colored with `GP_YELLOW_WARNING`).
    *   `ERROR_SYMBOL`: Keep `✗` (colored with `GP_RED_ERROR`).
    *   `INFO_SYMBOL`: `✧` (colored with `GP_CYAN_INTERACTIVE`) or `ⓘ` (colored with `GP_MINT_ACCENT`).
    *   `PROGRESS_SYMBOL`: `▸` (colored with `GP_LIGHT_BLUE_INFO`) or `…` (ellipsis).
    *   `NOTE_SYMBOL`: `♡` (colored with `GP_LAVENDER_PRIMARY`) or `•` (colored with `GP_PEACH_ACCENT`).
*   **Prompts:**
    *   Input Prompt Prefix: `↳` (colored with `GP_CYAN_INTERACTIVE`) or `›`.
*   **Spinner:**
    *   A sequence like `✿ ❀ ✾ ❁ ✽` (Flower Spinner from `arch/docs/ui.rust.md`).
    *   Alternative: `｡･ﾟﾟ･｡` cycling characters for a sparkle effect.

**4. Modifications to Existing Functions in `arch/modules/ui.py`**

The goal is to update the visual output of these functions, not necessarily their logic, to align with the new aesthetic.

*   **`print_header(title: str)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** `❄️ === {title} === ❄️` with `Colors.PINK_BG + Colors.CYAN`.
    *   **After (Proposed):** `print_color(f"✨ {title} ✨", Colors.PINK, bold=True)` or `print_color(f"🌸 {title} 🌸", Colors.MAGENTA, bold=True)`.
        This removes the background color for a cleaner look and uses a more thematic symbol and color.

*   **`print_section_header(title: str)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** Gradient text `--- {styled_title} ---` with `Colors.PURPLE`, `STAR_SYMBOL` prefix.
    *   **After (Proposed):**
        *   Keep the gradient text effect.
        *   Adjust gradient colors to: `[Colors.PINK, Colors.LAVENDER, Colors.PEACH]`.
        *   Change prefix/framing: `print_color(f"୨୧ {styled_title} ୨୧", Colors.LAVENDER, bold=True)` or `print_color(styled_title, Colors.LAVENDER, bold=True, prefix=f"{Colors.PEACH}✽{Colors.RESET}")`.

*   **`print_step_info(message: str)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** `Colors.LIGHT_BLUE` text, `INFO_SYMBOL` prefix.
    *   **After (Proposed):** `print_color(message, Colors.MINT, prefix=f"{Colors.MINT}ⓘ{Colors.RESET}")` (assuming `INFO_SYMBOL` is updated to `ⓘ`).

*   **`print_command_info(cmd_str: str)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** `Colors.CYAN` text, `PROGRESS_SYMBOL` (`→` in `Colors.BLUE`).
    *   **After (Proposed):** `print_color(f"running: {cmd_str}", Colors.LIGHT_BLUE, prefix=f"{Colors.LIGHT_BLUE}▸{Colors.RESET}")` (assuming `PROGRESS_SYMBOL` is updated to `▸`).

*   **`print_dry_run_command(cmd_str: str)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** `Colors.PEACH` text, `[DRY RUN]` prefix in `Colors.YELLOW`.
    *   **After (Proposed):** This is mostly fine. Consider changing the prefix color for softness: `prefix=f"{Colors.LAVENDER}[DRY RUN]{Colors.RESET}"`. Text color `Colors.PEACH` remains suitable.

*   **`Spinner` Class (`arch/modules/ui.py`)**
    *   **`__init__`:**
        *   Change default `spinner_chars` to `['✿', '❀', '✾', '❁', '✽']`.
    *   **`_spin` method:**
        *   The spinner character itself could be colored with `GP_PINK_PRIMARY` or `GP_MAGENTA_ACCENT`, while the message remains `GP_LIGHT_BLUE_INFO`.
        *   Example: `sys.stdout.write(f"\r{Colors.PINK}{spinner_char}{Colors.RESET} {Colors.LIGHT_BLUE}{self.message}{Colors.RESET} ")`

*   **`prompt_yes_no(question: str, ...)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** Question in `Colors.LAVENDER`. Suffix `[Y/n]` with `Y` in `Colors.PINK`.
    *   **After (Proposed):**
        *   Question color `Colors.LAVENDER` is good.
        *   Suffix: `f" [{Colors.MAGENTA}Y{Colors.RESET}/{Colors.LAVENDER}n{Colors.RESET}]"` (if default is yes) and `f" [{Colors.LAVENDER}y{Colors.RESET}/{Colors.MAGENTA}N{Colors.RESET}]"` (if default is no) to make the active choice pop more.
        *   Invalid input message: Change `Colors.ORANGE` to `Colors.PEACH`.

*   **`prompt_input(question: str, ...)` (`arch/modules/ui.py`)**
    *   **Before (Conceptual):** Question in `Colors.MINT`. Default value in `Colors.CYAN`.
    *   **After (Proposed):**
        *   Question color `Colors.MINT` is good.
        *   Default value highlight `Colors.CYAN` is fine, or `Colors.PEACH`.
        *   Add a gentle prompt prefix: `prompt_text: str = f"{Colors.CYAN}↳ {Colors.MINT}{question}{suffix}: {Colors.RESET}"`
        *   Empty input message: Change `Colors.ORANGE` to `Colors.PEACH`.

**5. New Minimal UI Helper Functions (Suggestions - Optional)**

*   **`print_separator(char: str = "·", color: str = Colors.LAVENDER, length: int = 50)`:**
    *   Prints a simple, soft separator line. Example: `print_color(char * length, color)`.
    *   Could be used to visually group related blocks of information subtly.

**6. Readability and Usability Considerations**

*   **Contrast:** Ensure all text has sufficient contrast against a standard dark terminal background.
*   **Minimalism:** The "girly pop" elements should enhance, not clutter or distract from, the core information.
*   **Consistency:** Apply the chosen colors and symbols consistently according to their defined roles.
*   **Accessibility:** Symbols should complement color cues, not be the sole indicators. Standard terminal fonts should support chosen Unicode characters.

**7. Conceptual Flow of UI Elements (Mermaid Diagram)**

```mermaid
graph TD
    A[Start Script] --> B{Installer Step};
    B -- Main Title --> C[print_header_girlypop];
    B -- Section Title --> D[print_section_header_girlypop];
    B -- Info Message --> E[print_step_info_girlypop];
    B -- Command Execution --> F[print_command_info_girlypop];
    B -- User Input Needed --> G{Prompt Type};
    G -- Yes/No --> H[prompt_yes_no_girlypop];
    G -- Text Input --> I[prompt_input_girlypop];
    B -- Long Operation --> J[Spinner_girlypop Start/Stop];
    J --> K[User sees themed spinner + message];
    C --> L[Styled Girly Pop Output];
    D --> L;
    E --> L;
    F --> L;
    H --> M[User provides input];
    I --> M;
    M --> B;
    B -- End Script --> N[Final Themed Message];

    classDef girlyPopStyle fill:#FFDAE9,stroke:#FF69B4,stroke-width:2px,color:#333;
    class C,D,E,F,H,I,J,K,L,N girlyPopStyle;