from typing import Iterable

from gradio.themes import Soft
from gradio.themes.utils import colors, fonts, sizes

gray = colors.Color(
    name="research-slate",
    c50="#f8fafc",
    c100="#f1f5f9",
    c200="#e2e8f0",
    c300="#cbd5e1",
    c400="#94a3b8",
    c500="#64748b",
    c600="#475569",
    c700="#334155",
    c800="#1e293b",
    c900="#0f172a",
    c950="#020617",
)

err_txt = "#f05656"
gradient = "linear-gradient(90deg, *primary_500 12%, *secondary_500 88%)"
gradient_muted = "linear-gradient(90deg, *primary_600 12%, *secondary_600 88%)"

err_dark = "rgba(228, 98, 98, 1)"
err_dark_muted = "rgba(228, 98, 98, 0.75)"

err = "rgba(255, 93, 93, 1)"
err_muted = "rgba(237, 80, 80, 1)"


common = dict(
    # element colours
    color_accent="*primary_500",
    # shadows
    shadow_drop="0 1px 3px rgba(15, 23, 42, 0.08)",
    shadow_drop_lg="0 14px 34px rgba(15, 23, 42, 0.12)",
    # layout atoms
    block_label_margin="*spacing_xl",
    block_label_padding="*spacing_xl",
    block_label_shadow="none",
    layout_gap="*spacing_xl",
    section_header_text_size="*text_lg",
    # buttons
    button_shadow="none",
    button_shadow_active="*shadow_drop",
    button_shadow_hover="none",
    # button_large_radius="*radius_xxl",
    # button_small_radius="*radius_xxl",
    # -----
)
dark_mode = dict(
    # body attributes
    body_text_color_subdued_dark="*neutral_400",
    # element colours
    background_fill_secondary_dark="*neutral_950",
    border_color_accent_dark="rgba(255,255,255,0)",
    border_color_primary_dark="*neutral_700",
    color_accent_soft_dark="*primary_900",
    # text
    link_text_color_dark="*secondary_200",
    link_text_color_active_dark="*secondary_300",
    link_text_color_visited_dark="*secondary_400",
    # layout atoms
    block_label_background_fill_dark="*neutral_900",
    block_label_border_width_dark="0px",
    block_label_text_color_dark="*primary_200",
    block_shadow_dark="none",
    block_title_text_color_dark="*primary_200",
    panel_border_width_dark="0px",
    # component atoms
    checkbox_background_color_selected_dark="*primary_400",
    checkbox_border_color_focus_dark="*primary_400",
    checkbox_border_color_selected_dark="*primary_500",
    checkbox_label_background_fill_selected_dark="*primary_200",
    checkbox_label_text_color_selected_dark="*neutral_700",
    error_border_color_dark=err_dark,
    error_text_color_dark="*neutral_100",
    error_icon_color_dark=err_dark,
    input_background_fill_dark="*neutral_800",
    input_border_color_dark="*input_background_fill",
    input_border_color_focus_dark="*input_background_fill",
    input_placeholder_color_dark="*neutral_500",
    loader_color_dark="*primary_200",
    slider_color_dark="*primary_300",
    stat_background_fill_dark="*secondary_100",
    table_border_color_dark="*neutral_800",
    table_even_background_fill_dark="*neutral_950",
    table_odd_background_fill_dark="*neutral_900",
    table_row_focus_dark="*neutral_800",
    # buttons
    button_primary_background_fill_dark=gradient,
    button_primary_background_fill_hover_dark=gradient_muted,
    button_secondary_background_fill_hover_dark="*neutral_700",
    button_cancel_background_fill_dark=err_dark,
    button_cancel_background_fill_hover_dark=err_dark_muted,
)
light_mode = dict(
    background_fill_primary="*neutral_50",
    background_fill_secondary="*neutral_100",
    # body attributes
    body_background_fill="*background_fill_primary",
    body_text_color_subdued="*neutral_600",
    border_color_accent="rgba(255,255,255,0)",
    border_color_primary="*neutral_300",
    color_accent_soft="*primary_100",
    # text
    link_text_color="*secondary_400",
    link_text_color_visited="*secondary_700",
    # layout atoms
    block_label_border_width="0px",
    block_label_background_fill="*neutral_50",
    block_label_text_color="*primary_700",
    block_shadow="none",
    block_title_text_color="*primary_700",
    panel_border_width="0px",
    # component atoms
    checkbox_background_color_selected="*primary_400",
    checkbox_border_color_focus="*primary_400",
    checkbox_border_color_selected="*primary_400",
    checkbox_label_border_color="*primary_200",
    error_background_fill="*background_fill_primary",
    error_border_color=err_muted,
    error_text_color="*neutral_800",
    input_background_fill="*neutral_100",
    input_border_color="*input_background_fill",
    input_border_color_focus="*input_background_fill",
    input_placeholder_color="*neutral_500",
    loader_color="*primary_300",
    slider_color="*primary_400",
    stat_background_fill="*secondary_100",
    table_even_background_fill="*neutral_100",
    table_odd_background_fill="*neutral_50",
    table_row_focus="*secondary_200",
    # buttons
    button_primary_background_fill=gradient_muted,
    button_primary_background_fill_hover=gradient,
    button_secondary_background_fill="*neutral_100",
    button_secondary_background_fill_hover="*neutral_200",
    button_cancel_background_fill=err_muted,
    button_cancel_background_fill_hover=err,
    button_cancel_text_color="*neutral_50",
)


class Kotaemon(Soft):
    """
    Official theme of Slides.
    Public version: https://huggingface.co/spaces/lone17/kotaemon
    """

    def __init__(
        self,
        *,
        primary_hue: colors.Color | str = colors.teal,
        secondary_hue: colors.Color | str = colors.sky,
        neutral_hue: colors.Color | str = gray,
        spacing_size: sizes.Size | str = sizes.spacing_md,
        radius_size: sizes.Size | str = sizes.radius_md,
        text_size: sizes.Size | str = sizes.text_md,
        font: fonts.Font
        | str
        | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("Plus Jakarta Sans"),
            "Manrope",
            "ui-sans-serif",
            "sans-serif",
        ),
        font_mono: fonts.Font
        | str
        | Iterable[fonts.Font | str] = (
            fonts.GoogleFont("IBM Plex Mono"),
            "ui-monospace",
            "monospace",
        ),
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )
        self.name = "slides"
        super().set(
            **common,
            **dark_mode,
            **light_mode,
        )
