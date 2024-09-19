/**
 * This is the default configuration file for the Superdesk application. By default,
 * the app will use the file with the name "superdesk.config.js" found in the current
 * working directory, but other files may also be specified using relative paths with
 * the SUPERDESK_CONFIG environment variable or the grunt --config flag.
 */
module.exports = function(grunt) {
    return {
        apps: [
            'superdesk-planning',
        ],
        importApps: [
            '../index',
            'superdesk-planning',
        ],
        defaultRoute: '/workspace/personal',
        features: {
            swimlane: {defaultNumberOfColumns: 4},
            noTakes: true,
            planning: true,
        },
        validatorMediaMetadata: {
            headline: {required: true},
            alt_text: {required: true},
            description_text: {required: true},
            copyrightholder: {required: false},
            byline: {required: false},
            usageterms: {required: false},
            copyrightnotice: {required: false}
        },
        workspace: {
            planning: true,
            assignments: true,
        },
        planning_default_view: 'PLANNING',
        profileLanguages: [
            'en',
            'fi_FI',
        ],
    };
};
