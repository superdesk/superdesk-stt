import { startApp } from 'superdesk-core/scripts/index';
import newshub from './stt/newshub';
import './stt.css';

setTimeout(() => {
  startApp(
    [
      {
        id: 'planning-extension',
        load: () => import('superdesk-planning/client/planning-extension'),
      },
      {
        id: 'ai-widget',
        load: () =>
          import('superdesk-core/scripts/extensions/ai-widget').then(
            (widget) => {
              widget.configure((superdesk) => ({
                translations: {
                  translateActionIntegration: true,
                  generateTranslations: (article, language) => {
                    return superdesk
                      .httpRequestJsonLocal({
                        method: 'POST',
                        path: '/stt/ai',
                        payload: {
                          language: language,
                          text: article.body_html,
                          type: 'translation',
                        },
                      })
                      .then((result) => result.response)
                      .catch((err) => {
                        console.error('Error generating translations:', err);
                        return '';
                      });
                  },
                },
                generateHeadlines: (article) => {
                  return superdesk
                    .httpRequestJsonLocal({
                      method: 'POST',
                      path: '/stt/ai',
                      payload: {
                        text: article.body_html,
                        type: 'headlines',
                      },
                    })
                    .then((result) => {
                      return result.response;
                    })
                    .catch((err) => {
                      console.error('Error generating headlines:', err);
                      return [];
                    });
                },
              }));

              return widget;
            }
          ),
      },
    ],
    {}
  );
});

export default angular.module('stt', [newshub.name]);
