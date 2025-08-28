import {IExtension, IExtensionActivationResult} from 'superdesk-api';

const extension: IExtension = {
    activate: (superdesk) => {
        const {gettext} = superdesk.localization;

        return Promise.resolve({
            contributions: {
                monitoring: {
                    listFiltersConfig: [
                        {
                            label: gettext('Content Profile'),
                            fieldId: 'contentProfile',
                            getOptions: () => superdesk.entities.contentProfile
                                .getAll().map((x) => ({id: x._id, label: x.label})),
                            selectMultiple: true,
                            operator: 'OR',
                        },
                        {
                            label: gettext('Categories'),
                            fieldId: 'anpa_category.qcode',
                            getOptions: () => superdesk.entities.vocabulary
                                .getAll().get('sttdepartment').items.map((x) => ({id: x.qcode, label: x.name})),
                            selectMultiple: true,
                            operator: 'OR',
                        },
                    ]
                },
            },
        } satisfies IExtensionActivationResult);
    },
};

export default extension;
