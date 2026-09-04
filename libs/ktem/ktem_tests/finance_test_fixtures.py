def quick_ratio_prompt() -> str:
    return (
        "Does 3M have a reasonably healthy liquidity profile based on its quick "
        "ratio for Q2 of FY2023?"
    )


def quick_ratio_evidence_metadata() -> dict:
    return {
        "evidence": [
            {
                "evidence_id": "balance-sheet-table",
                "file_id": "file-1",
                "page_label": "4",
                "cell_id": cell_id,
                "evidence_level": "cell",
                "modality": "table",
                "row_label": row_label,
                "column_label": "Q2 FY2023",
                "period": "2023",
                "value": value,
                "unit": "USD",
                "scale": "million",
                "statement_kind": "balance_sheet",
                "financial_scope": "consolidated",
                "text": f"{row_label} Q2 FY2023 {value} USD million.",
            }
            for cell_id, row_label, value in (
                ("current-assets-q2-2023", "Total current assets", "15754"),
                ("inventories-q2-2023", "Total inventories", "5280"),
                (
                    "current-liabilities-q2-2023",
                    "Total current liabilities",
                    "10936",
                ),
            )
        ]
    }
