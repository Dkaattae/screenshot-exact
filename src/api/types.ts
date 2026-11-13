export type Slot = 'top' | 'one_piece' | 'bottom' | 'outer' | 'accessory';
export type View = 'front' | 'side' | 'back';
export type Layer = 'base' | 'outer' | 'accessory';
export type JobStatus = 'queued' | 'running' | 'done' | 'failed';
export interface BodyProfile { id: string; user_id: string; height_cm: number | null; images: Record<View,string>; measurements: Record<string,number|null>; consent_at: string; updated_at: string }
export interface DefaultBody { id: string; name: string; images: Record<View,string> }
export interface Background { id: string; name: string; url: string; is_preset: boolean }
export interface Item { id: string; user_id: string; slot: Slot; name: string; front_url: string; back_url: string|null; measurements: Record<string,number|null>; created_at: string }
export interface OutfitState { body: {kind:'user'|'default';id:string}; background_id:string; base: {mode:'top_bottom';top_id:string;bottom_id:string|null;tucked:boolean}|{mode:'one_piece';one_piece_id:string}; outer:{item_id:string;open:boolean}|null; accessory:{item_id:string}|null; views:View[]; style_notes:Record<string,string> }
export interface Outfit {id:string;user_id:string;name:string|null;favorite:boolean;state:OutfitState;version:number;created_at:string;updated_at:string}
export interface Job {id:string;outfit_id:string;outfit_version:number;status:JobStatus;views:Record<View,{status:JobStatus;url:string|null}>;layers:{layer:Layer;reused:boolean}[];timings_ms:{total:number|null};cost_usd:number|null;error:string|null;created_at:string}
export interface ApiError {error:{code:string;message:string}}
