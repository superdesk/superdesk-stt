def init_app(app):
    from .enrich_events import format_kiirelisays_for_export

    app.jinja_env.globals.update(
        format_kiirelisays_for_export=format_kiirelisays_for_export
    )
