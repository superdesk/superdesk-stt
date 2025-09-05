def init_app(app):
    from .enrich_related import enrich_planning_agendas

    app.jinja_env.globals.update(enrich_planning_agendas=enrich_planning_agendas)
