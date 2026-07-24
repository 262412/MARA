from ktem.reasoning.mara_ragtruth_claims import (
    heuristic_unsupported_claim_indices,
    supported_claim_indices,
)


def test_lexical_support_accepts_paraphrase_but_not_changed_number():
    source = (
        "ISIS has taken the east of the city, making it inaccessible from the "
        "only safe route to neighboring Anbar province. Revenue was 20 million."
    )

    assert supported_claim_indices(
        source,
        [
            (
                "ISIS has taken control of the east of the city, cutting off "
                "the only safe route to neighboring Anbar province."
            ),
            "Revenue was 30 million.",
        ],
    ) == {0}


def test_lexical_support_rejects_new_superlative_qualifier():
    source = "The F1 circuit was built for the Las Vegas race."
    claim = "The F1 circuit is the longest circuit ever built for the Las Vegas race."

    assert supported_claim_indices(source, [claim]) == set()


def test_lexical_support_accepts_close_summary_paraphrase():
    source = (
        "She was the youngest of eight children and became famous as the "
        "youngest performer in the Partridge family band."
    )
    claim = (
        "She was the youngest of eight children and rose to fame as the "
        "youngest member of the Partridge family band."
    )

    assert supported_claim_indices(source, [claim]) == {0}


def test_qualifier_check_treats_each_and_every_as_equivalent():
    source = (
        "Joint patrols could make the border safer. Agents encounter 2,500 "
        "migrants each weekend."
    )
    claim = (
        "Joint patrols could make the border safer, but 2,500 migrants are "
        "encountered every weekend."
    )

    assert supported_claim_indices(source, [claim]) == {0}


def test_passage_support_recognizes_advice_paraphrase():
    source = str(
        {
            "question": "what happens when lightning hits your phone",
            "passages": (
                "If lightning strikes the phone line, it can travel to every "
                "phone. During a lightning storm, stay off the phone. Use a "
                "cordless or cell phone instead."
            ),
        }
    )
    claim = (
        "It is advised to avoid using landline phones during a lightning storm "
        "and instead use cordless or cell phones."
    )

    assert supported_claim_indices(source, [claim]) == {0}
    assert heuristic_unsupported_claim_indices(source, [claim]) == set()


def test_structured_field_comparison_checks_values_unknowns_and_counts():
    source = str(
        {
            "name": "Cafe Example",
            "hours": {"Monday": "0:0-0:0"},
            "attributes": {
                "WiFi": "no",
                "OutdoorSeating": False,
                "RestaurantsReservations": None,
            },
            "review_info": [
                {"review_text": "First review."},
                {"review_text": "Second review."},
            ],
        }
    )
    claims = [
        "Cafe Example offers free Wi-Fi.",
        "Cafe Example does not have outdoor seating.",
        "Cafe Example is open on Monday.",
        "Cafe Example has four customer reviews.",
        "Cafe Example does not accept reservations.",
    ]

    assert heuristic_unsupported_claim_indices(source, claims) == {0, 2, 3}
    assert supported_claim_indices(source, claims) == {1}


def test_structured_support_checks_all_fields_in_compound_claim():
    source = str(
        {
            "name": "Silvergreens",
            "attributes": {
                "WiFi": "free",
                "RestaurantsGoodForGroups": True,
                "RestaurantsReservations": False,
            },
        }
    )
    claim = (
        "The restaurant provides free Wi-Fi and is good for groups, but does "
        "not take reservations."
    )

    assert supported_claim_indices(source, [claim]) == {0}
    assert heuristic_unsupported_claim_indices(source, [claim]) == set()


def test_missing_structured_field_is_unknown_not_a_conflict():
    source = str({"name": "Cafe Example", "attributes": {}})
    claim = "Cafe Example offers free Wi-Fi."

    assert supported_claim_indices(source, [claim]) == set()
    assert heuristic_unsupported_claim_indices(source, [claim]) == set()


def test_structured_review_text_can_support_missing_hours_field():
    source = str(
        {
            "name": "Merci Montecito",
            "hours": {"Monday": "9:0-16:0"},
            "review_info": [
                {
                    "review_text": (
                        "My only complaint is that they are closed on Sunday."
                    )
                }
            ],
        }
    )
    claim = (
        "However, the business is closed on Sundays, which was a "
        "disappointment for this customer."
    )

    assert supported_claim_indices(source, [claim]) == {0}
    assert heuristic_unsupported_claim_indices(source, [claim]) == set()


def test_response_headers_and_source_limit_notes_are_nonfactual():
    source = str(
        {
            "question": "How do I install tile?",
            "passages": "Rinse the floor and let it dry for 48 hours.",
        }
    )
    claims = [
        "Here's my answer based on the provided passages:",
        "How do I install tile?",
        (
            "Please note that the passages do not mention how to handle an "
            "uneven floor."
        ),
        (
            "The passages do not provide detailed instructions for managing "
            "the falling tree."
        ),
        ("Additionally, there may be local regulations or safety " "considerations."),
        "It is always best to consult with a professional arborist.",
        (
            "If the passages did not contain the necessary information, I "
            'would have replied with "Unable to answer."'
        ),
        ("However, the passages do not directly mention the cardiovascular " "system."),
        "Therefore, I cannot answer based solely on the provided passages.",
    ]

    assert supported_claim_indices(source, claims) == set(range(len(claims)))
    assert heuristic_unsupported_claim_indices(source, claims) == set()


def test_question_restatement_is_supported_as_answer_section_intro():
    source = str(
        {
            "question": "How do I stop a horse from kicking?",
            "passages": "Move the horse away and use a firm verbal command.",
        }
    )
    claim = "To stop a horse from kicking, you can use several strategies."

    assert supported_claim_indices(source, [claim]) == {0}
    assert heuristic_unsupported_claim_indices(source, [claim]) == set()
