"""Candidate pypdf 6.19.0 PageLabels dictionary behavior."""

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from kotaemon.loaders import AutoReader

from .test_pdf_reading_contracts import PAGE_TEXT, write_pdf


@pytest.mark.parametrize(
    "start,expected",
    [
        (26, ["Z", "AA", "BB"]),
        (27, ["AA", "BB", "CC"]),
        (28, ["BB", "CC", "DD"]),
        (52, ["ZZ", "AAA", "BBB"]),
        (53, ["AAA", "BBB", "CCC"]),
    ],
)
def test_official_uppercase_labels_use_repeated_letters_at_boundaries(
    tmp_path, start, expected
):
    source = write_pdf(
        tmp_path / "boundary.pdf",
        [{"startpage": 0, "style": "A", "firstpagenum": start}],
    )
    pdf = PdfReader(source)
    dictionary = pdf.trailer["/Root"]["/PageLabels"]["/Nums"][1].get_object()
    assert dictionary["/S"] == "/A" and dictionary["/St"] == start
    assert pdf.page_labels == expected
    documents = AutoReader("PDFReader").load_data(source)
    assert [doc.text.strip() for doc in documents] == PAGE_TEXT
    assert [doc.metadata["page_label"] for doc in documents] == expected


def test_lowercase_prefix_and_numbering_restart_follow_actual_dictionary(tmp_path):
    source = write_pdf(
        tmp_path / "restart.pdf",
        [
            {"startpage": 0, "style": "a", "prefix": "Sec-", "firstpagenum": 27},
            {"startpage": 2, "style": "a", "prefix": "Sec-", "firstpagenum": 1},
        ],
    )
    pdf = PdfReader(source)
    entries = pdf.trailer["/Root"]["/PageLabels"]["/Nums"]
    assert [int(entries[index]) for index in (0, 2)] == [0, 2]
    assert entries[1].get_object()["/P"] == "Sec-"
    assert pdf.page_labels == ["Sec-aa", "Sec-bb", "Sec-a"]


@pytest.mark.parametrize(
    "style,start,prefix",
    [
        ("/A", NumberObject(-5), TextStringObject("")),
        ("/A", NumberObject(10**12), TextStringObject("")),
        ("/A", TextStringObject("bad"), TextStringObject("")),
        ("/A", NumberObject(1), NumberObject(7)),
        ("/Unknown", NumberObject(1), TextStringObject("")),
        ("/R", NumberObject(4000), TextStringObject("")),
    ],
)
def test_malformed_or_bounded_large_label_values_fall_back_to_physical_position(
    tmp_path, caplog, style, start, prefix
):
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=216, height=144)
    writer._root_object[NameObject("/PageLabels")] = DictionaryObject(
        {
            NameObject("/Nums"): ArrayObject(
                [
                    NumberObject(0),
                    DictionaryObject(
                        {
                            NameObject("/S"): NameObject(style),
                            NameObject("/St"): start,
                            NameObject("/P"): prefix,
                        }
                    ),
                ]
            )
        }
    )
    source = tmp_path / "malformed-labels.pdf"
    writer.write(source)
    assert PdfReader(source).page_labels == ["1", "2", "3"]
    assert "Ignoring" in caplog.text
