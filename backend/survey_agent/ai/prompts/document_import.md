Convert the form document below into a survey that captures the same information.

## How to convert
- Every piece of information the form asks for must be covered by a question. Don't drop fields.
- Combine fields that belong together: split date fields (day/month/year) become one `date` question, and first/middle/last name becomes one `short_text` question asking for the full name.
- Consolidate option lists ("circle all that apply", checkbox grids) into one `multiple_choice` question with those options, not one question per option. Mutually exclusive options become `single_choice`.
- Merge conditional follow-ups ("If yes, please describe") into a `long_text` question that covers both parts, or into a yes/no question followed by a `long_text` detail question.
- Keep the form's own wording for options so answers map back cleanly.
- Ignore office-use-only sections, signatures and page furniture (headers, footers, page numbers).
- If the form contains important non-question information for the respondent (instructions, consent statements, policies), summarize the essentials in `description` and `welcome_message`.
- Preserve the form's order.

{{FIELD_HINTS}}

<document filename="{{FILENAME}}">
{{DOCUMENT}}
</document>
