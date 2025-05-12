import {startApp} from 'superdesk-core/scripts/index';
import './stt.css';

setTimeout(() => {
    startApp([
        {
            id: 'planning-extension',
            load: () => import('superdesk-planning/client/planning-extension'),
        },
    ], {});
});

export default angular.module('stt.superdesk', []);

