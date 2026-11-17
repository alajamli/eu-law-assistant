"""Parser tests, built from the markup the Cellar endpoint actually returns.

The fixture keeps the awkward parts of the real document: the paragraph marker
`(a)` in its own table cell, the inline `1.` numbering, nested chapter headings,
and a recital that is not an article.
"""

from ingest.parse import count_articles, parse_html

DOC_TITLE = "General Data Protection Regulation"

FIXTURE = """
<html><body>
  <p class="oj-normal">Whereas:</p>

  <div class="eli-subdivision" id="rct_12">
    <table><tr>
      <td><p class="oj-normal">(12)</p></td>
      <td><p class="oj-normal">This Regulation respects fundamental rights.</p></td>
    </tr></table>
  </div>

  <div class="eli-subdivision" id="enc_1">
    <div id="cpt_II">
      <p class="oj-ti-section-1"><span class="oj-italic">CHAPTER II</span></p>
      <div class="eli-title">
        <p class="oj-ti-section-2"><span class="oj-bold"><span class="oj-italic">Principles</span></span></p>
      </div>

      <div class="eli-subdivision" id="art_5">
        <p class="oj-ti-art">Article 5</p>
        <div class="eli-title" id="art_5.tit_1">
          <p class="oj-sti-art">Principles relating to processing of personal data</p>
        </div>
        <div id="005.001">
          <p class="oj-normal">1. Personal data shall be:</p>
          <table>
            <tr><td><p class="oj-normal">(a)</p></td><td><p class="oj-normal">processed lawfully;</p></td></tr>
            <tr><td><p class="oj-normal">(b)</p></td><td><p class="oj-normal">collected for specified purposes;</p></td></tr>
          </table>
        </div>
      </div>

      <div class="eli-subdivision" id="art_6">
        <p class="oj-ti-art">Article 6</p>
        <p class="oj-normal">Processing shall be lawful only if one of the following applies.</p>
      </div>
    </div>
  </div>
</body></html>
"""


def test_markers_are_merged_into_their_body_text():
    units = parse_html(FIXTURE, DOC_TITLE)
    articles = [u for u in units if not u.is_recital]
    assert [(u.article, u.paragraph) for u in articles] == [
        ("5", "1"),
        ("5", "a"),
        ("5", "b"),
        ("6", None),
    ]
    assert "processed lawfully" in articles[1].text
    assert articles[1].text != "(a)"


def test_chapter_and_section_are_tracked():
    first_article = next(u for u in parse_html(FIXTURE, DOC_TITLE) if not u.is_recital)
    assert first_article.chapter == "CHAPTER II"
    assert first_article.section == "Principles"


def test_article_title_is_captured():
    first_article = next(u for u in parse_html(FIXTURE, DOC_TITLE) if not u.is_recital)
    assert first_article.title == "Principles relating to processing of personal data"


def test_recital_is_flagged_and_not_counted_as_an_article():
    units = parse_html(FIXTURE, DOC_TITLE)
    recital = next(u for u in units if u.is_recital)
    assert recital.article == "12"
    assert recital.paragraph is None
    assert "fundamental rights" in recital.text
    assert count_articles(units) == 2


def test_breadcrumb_names_the_article_and_its_title():
    first_article = next(u for u in parse_html(FIXTURE, DOC_TITLE) if not u.is_recital)
    assert first_article.breadcrumb(DOC_TITLE) == (
        f"{DOC_TITLE} > CHAPTER II > Principles > Article 5(1) "
        "— Principles relating to processing of personal data"
    )


def test_fallback_split_when_there_is_no_eli_markup():
    flat = "Article 5\nProhibited practices text.\nArticle 6\nHigh-risk text."
    units = parse_html(f"<html><body><p>{flat}</p></body></html>", DOC_TITLE)
    assert [(u.article, u.paragraph) for u in units] == [("5", None), ("6", None)]


def test_empty_document_does_not_raise():
    assert parse_html("<html><body></body></html>", DOC_TITLE) == []


def test_footnote_markers_are_stripped():
    html = (
        '<html><body><div class="eli-subdivision" id="art_1">'
        '<p class="oj-normal">Obligation<a href="#n1"><span class="oj-super oj-note-tag">3</span></a> applies.</p>'
        "</div></body></html>"
    )
    units = parse_html(html, DOC_TITLE)
    assert units[0].text == "Obligation applies."


FR_INLINE = """
<html><body><div class="eli-subdivision" id="art_5">
  <p class="oj-ti-art">Article 5</p>
  <p class="oj-normal">1. Les données à caractère personnel doivent être:
     a) traitées de manière licite et transparente au regard de la personne concernée;
     b) collectées pour des finalités déterminées et légitimes;
     c) adéquates, pertinentes et limitées à ce qui est nécessaire.</p>
</div></body></html>
"""


def test_french_inline_list_items_become_separate_units():
    """The FR rendering inlines `a) … ; b) …` where EN uses table cells."""
    units = parse_html(FR_INLINE, DOC_TITLE)
    assert [(u.article, u.paragraph) for u in units] == [
        ("5", "1"),
        ("5", "a"),
        ("5", "b"),
        ("5", "c"),
    ]
    assert units[0].text.endswith("doivent être:")
    assert units[1].text.startswith("traitées de manière licite")


def test_inline_split_does_not_fire_on_ordinary_prose():
    html = (
        '<html><body><div class="eli-subdivision" id="art_2">'
        '<p class="oj-normal">This applies; the following rules apply.</p>'
        "</div></body></html>"
    )
    assert len(parse_html(html, DOC_TITLE)) == 1
