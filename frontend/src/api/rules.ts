import type { OutfitState, Layer } from './types';
export const VIEWS = ['front','side','back'] as const;
export function validation(state:OutfitState):string[] {
 const errors:string[]=[];
 if(state.base.mode==='top_bottom') {if(!state.base.top_id) errors.push('Choose a top.');if(!state.base.bottom_id) errors.push('Choose a bottom.');}
 else if(!state.base.one_piece_id) errors.push('Choose a one-piece.');
 if(!state.body.id) errors.push('Choose a body.');
 if(!state.background_id) errors.push('Choose a background.');
 return errors;
}
export function editState(state:OutfitState,message:string):{state:OutfitState;change_summary:string} {
 const next=structuredClone(state);const text=message.toLowerCase();let summary='That request wasn’t understood. Try “tuck the shirt” or “open the jacket”.';
 if(next.base.mode==='top_bottom' && /untuck|tuck/.test(text)){next.base.tucked=!text.includes('untuck');summary=next.base.tucked?'Shirt tucked in.':'Shirt untucked.';}
 else if(next.outer && /open|clos/.test(text)){next.outer.open=text.includes('open');summary=next.outer.open?'Outer layer opened.':'Outer layer closed.';}
 return {state:next,change_summary:summary};
}
export function reusedLayers(previous:OutfitState|undefined,next:OutfitState):{layer:Layer;reused:boolean}[] {
 const same=(a:unknown,b:unknown)=>JSON.stringify(a)===JSON.stringify(b);
 const common=!!previous && same(previous.base,next.base)&&same(previous.body,next.body)&&previous.background_id===next.background_id&&same(previous.style_notes,next.style_notes);
 return [{layer:'base',reused:common},{layer:'outer',reused:common&&same(previous?.outer,next.outer)},{layer:'accessory',reused:common&&same(previous?.outer,next.outer)&&same(previous?.accessory,next.accessory)}];
}
