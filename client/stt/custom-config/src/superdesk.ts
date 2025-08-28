import {ISuperdesk} from 'superdesk-api';

// @ts-ignore
export const superdesk: ISuperdesk = window['extensionsApiInstances']['custom-config'] as ISuperdesk;
