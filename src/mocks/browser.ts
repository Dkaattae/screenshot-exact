import {setupWorker} from 'msw/browser';
import {handlers} from './handlers';
const worker=setupWorker(...handlers);
export async function startMocks(){await worker.start({onUnhandledRequest:'bypass',quiet:true});}
