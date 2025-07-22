/**
 * This is the default configuration file for the Superdesk application. By default,
 * the app will use the file with the name "superdesk.config.js" found in the current
 * working directory, but other files may also be specified using relative paths with
 * the SUPERDESK_CONFIG environment variable or the grunt --config flag.
 */
module.exports = function (grunt) {
  return {
    /* enable modules */
    apps: ["superdesk-planning", "superdesk.analytics", "stt"],
    importApps: ["../index", "superdesk-planning", "superdesk-analytics"],
    workspace: {
      planning: true,
      assignments: true,
      analytics: true,
    },

    vocabulariesToExcludeAsFields: ['sttsubj'],

    authoring: {
        customEditorTags: [
            {
                id: 'company',
                icon: 'business',
                label: 'Yritys',
                borderColor: 'orange',
            },
            {
                id: 'person',
                icon: 'user',
                label: 'Henkilö',
                borderColor: 'blue',
            },
        ],
    },

    /* landing page after login */
    defaultRoute: "/workspace/monitoring",

    /* enable changing content profile for stories */
    item_profile: {
      change_profile: 1,
    },

    /* timezone and date time formats */
    defaultTimezone: "Europe/Helsinki",
    shortTimeFormat: "HH:mm, DD.MM.YYYY",
    shortDateFormat: "HH:mm, DD.MM.YYYY",
    shortWeekFormat: "HH:mm, DD.MM.YYYY",
    /* date time formats in list views */
    view: {
      timeformat: "HH:mm",
      dateformat: "DD.MM.YYYY",
    },

    features: {
      swimlane: { defaultNumberOfColumns: 4 },
      noTakes: true /* hide takes */,
      noMissingLink: true /* display of the missing link warning (based on slugline) */,
      hideCreatePackage: true /* hide packages */,
      planning: true /* display planning */,
      searchShortcut: true /* display search shortcuts */,
      elasticHighlight: true /* highligt search terms in results */,
      noPublishOnAuthoringDesk: true /* disable publishing from authoring desks */,
      customAuthoringTopbar: {
        /* story workflow shortcuts */
        toDesk: false /* send to next stage of current desk */,
        publish: false /* publish */,
        publishAndContinue: false /* publish and create update */,
        closeAndContinue: false /* save, close, and update */,
      },
      confirmDueDate: true /* confirm due date */,
    },

    /* list of CVs which are searched */
    search_cvs: [
      { id: "sttgenre", name: "STT genre", field: "subject", list: "sttgenre" },
      {
        id: "sttdepartment",
        name: "Department",
        field: "subject",
        list: "sttdepartment",
      },
      { id: "sttsubj", name: "Subject", field: "subject", list: "sttsubj" },
    ],
    /* list of fields which are searched */
    search: {
      slugline: 1,
      headline: 1,
      unique_name: 1,
      story_text: 1,
      byline: 0,
      keywords: 1,
      creator: 1,
      from_desk: 1,
      to_desk: 1,
      spike: 1,
      ingest_provider: 1,
      marked_desks: 1,
      scheduled: 1,
    },

    /* configuration of list view */
    list: {
      priority: ["urgency"],
      firstLine: [
        "slugline",
        "highlights",
        "markedDesks",
        "headline",
        "wordcount",
        "associations",
        "publish_queue_errors",
        "versioncreated",
      ],
      secondLine: [
        "profile",
        "state",
        "update",
        "scheduledDateTime",
        "embargo",
        "takekey",
        "signal",
        "flags",
        "updated",
        "provider",
        "desk",
        "fetchedDesk",
        "associatedItems",
      ],
    },

    /* configuration of monitoring features */
    monitoring: {
      scheduled: {
        sort: {
          default: { field: "publish_schedule", order: "asc" },
          allowed_fields_to_sort: ["publish_schedule"],
        },
      },
    },
    /* configuration of assignments view */
    assignmentsList: {
      firstLine: ["slugline", "name"],
      secondLine: [
        "priority",
        "state",
        "accepted",
        "content",
        "internal",
        "due_date",
        "desk",
        "genre",
      ],
    },

    /* display alternative labels for some stings */
    langOverride: {
      en: {
        slugline: "topic",
        Slugline: "Topic",
        SLUGLINE: "TOPIC",
      },
    },
    planning_default_view: 'PLANNING',
    profileLanguages: [
      'en',
      'fi_FI',
    ],
    spellchecking: {
      spellcheckersByLanguage: {
        fi: {
          spellcheckerId: 'stt_fin',
          runningMode: 'initially-disabled',
        },
      },
    },
  };
}
