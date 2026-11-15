from .openapi import FILE, text


def test_the_frontends_openapi_document_is_current():
    # the frontend's API types (src/api/schema.ts) are generated from it
    assert FILE.read_text() == text(), "The API changed: run `npm run gen:api` in frontend."
