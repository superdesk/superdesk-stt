def init_app(app):
    from .common import format_paivalista_for_export

    app.jinja_env.globals.update(
        format_paivalista_for_export=format_paivalista_for_export
    )
