from pptmaker.blueprint.models import BlueprintReview, DeckBlueprint


def review_blueprint(
    blueprint: DeckBlueprint,
    known_fact_ids: set[str],
) -> BlueprintReview:
    defects = []
    pages = blueprint.pages
    page_ids = [page.page_id for page in pages]

    if len(page_ids) != len(set(page_ids)):
        defects.append("duplicate_page_ids")
    if [page.order for page in pages] != list(range(1, len(pages) + 1)):
        defects.append("page_order_invalid")

    titles = [" ".join(page.conclusion_title.lower().split()) for page in pages]
    if len(titles) != len(set(titles)):
        defects.append("duplicate_titles")

    section_page_ids = [
        page_id
        for section in blueprint.sections
        for page_id in section.page_ids
    ]
    if any(page_id not in set(page_ids) for page_id in section_page_ids):
        defects.append("section_page_missing")
    if set(section_page_ids) != set(page_ids):
        defects.append("section_page_coverage_invalid")

    referenced_facts = {
        fact_id
        for page in pages
        for fact_id in page.fact_ids
    }
    if referenced_facts - known_fact_ids:
        defects.append("unknown_fact_reference")

    heavy_run = 0
    for page in pages:
        slot_ids = [item.slot_id for item in page.asset_slots]
        element_ids = [item.element_id for item in page.layout_elements]
        image_refs = {
            item.content_ref
            for item in page.layout_elements
            if item.kind == "image"
        }
        if len(page.asset_slots) > 4:
            defects.append("too_many_asset_slots")
        if len(slot_ids) != len(set(slot_ids)):
            defects.append("duplicate_asset_slot_id")
        if len(element_ids) != len(set(element_ids)):
            defects.append("duplicate_layout_element_id")
        if image_refs - set(slot_ids):
            defects.append("invalid_layout_reference")
        if set(slot_ids) - image_refs:
            defects.append("unrepresented_asset_slot")
        if any(
            item.required
            and not item.selected_asset_id
            and item.fallback == "no_image"
            for item in page.asset_slots
        ):
            defects.append("required_asset_missing")

        heavy_run = heavy_run + 1 if page.density == "heavy" else 0
        if heavy_run > 3:
            defects.append("density_rhythm_invalid")
            break

    return BlueprintReview(passed=not defects, defects=defects)
