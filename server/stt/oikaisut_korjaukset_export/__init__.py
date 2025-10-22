def init_app(app):
    from .enrich_items import enrich_oikaisut_korjaukset_for_export

    app.jinja_env.globals.update(
        enrich_oikaisut_korjaukset_for_export=enrich_oikaisut_korjaukset_for_export
    )
