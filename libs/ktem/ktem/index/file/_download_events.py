from __future__ import annotations


def register_download_events(page, *, sso_enabled: bool) -> None:
    if not sso_enabled:
        page.download_all_button.click(
            fn=page.download_all_files,
            inputs=[],
            outputs=page.download_all_button,
            show_progress="hidden",
        )
        page.download_single_button.click(
            fn=page.download_single_file,
            inputs=[
                page.is_zipped_state,
                page.selected_file_id,
                page._app.user_id,
            ],
            outputs=[page.is_zipped_state, page.download_single_button],
            show_progress="hidden",
        )
        return

    page.download_single_button.click(
        fn=page.download_single_file_simple,
        inputs=[
            page.is_zipped_state,
            page.chunks,
            page.selected_file_id,
            page._app.user_id,
        ],
        outputs=[page.is_zipped_state, page.download_single_button],
        show_progress="hidden",
    )


__all__ = ["register_download_events"]
