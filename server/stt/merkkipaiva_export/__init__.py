def init_app(app):
    from .common import format_merkkipaiva_for_export

    app.jinja_env.globals.update(
        format_merkkipaiva_for_export=format_merkkipaiva_for_export
    )
