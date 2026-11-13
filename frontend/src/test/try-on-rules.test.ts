import {describe,it,expect} from 'vitest';import {validation,editState,reusedLayers} from '@/api/rules';import type {OutfitState} from '@/api/types';
const state:OutfitState={body:{kind:'default',id:'body'},background_id:'background',base:{mode:'top_bottom',top_id:'top',bottom_id:'bottom',tucked:false},outer:{item_id:'jacket',open:false},accessory:{item_id:'bag'},style_notes:{}};
describe('Outfit rules',()=>{
 it('requires both top and bottom in top mode',()=>expect(validation({...state,base:{mode:'top_bottom',top_id:'',bottom_id:null,tucked:false}})).toEqual(['Choose a top.','Choose a bottom.']));
 it('requires a one-piece without requiring a bottom',()=>{expect(validation({...state,base:{mode:'one_piece',one_piece_id:'dress'}})).toEqual([]);expect(validation({...state,base:{mode:'one_piece',one_piece_id:''}})).toEqual(['Choose a one-piece.']);});
 it('requires a chosen body',()=>expect(validation({...state,body:{kind:'default',id:''}})).toEqual(['Choose a body.']));
 it('requires a background',()=>expect(validation({...state,background_id:''})).toEqual(['Choose a background.']));
 it('recognizes tuck and untuck distinctly',()=>{expect(editState(state,'tuck the shirt').state.base).toEqual({...state.base,tucked:true});expect(editState({...state,base:{mode:'top_bottom',top_id:'top',bottom_id:'bottom',tucked:true}},'untuck').state.base).toEqual(state.base);});
 it('recognizes opening and closing an outer layer',()=>{expect(editState(state,'open jacket').state.outer?.open).toBe(true);expect(editState({...state,outer:{item_id:'jacket',open:true}},'close jacket').state.outer?.open).toBe(false);});
 it('does not add outer controls to an outfit without an outer',()=>expect(editState({...state,outer:null},'open jacket').state.outer).toBeNull());
 it('reuses base when only outer open changes',()=>expect(reusedLayers(state,{...state,outer:{item_id:'jacket',open:true}})).toEqual([{layer:'base',reused:true},{layer:'outer',reused:false},{layer:'accessory',reused:false}]));
 it('reuses base and outer when only accessory changes',()=>expect(reusedLayers(state,{...state,accessory:{item_id:'new bag'}})).toEqual([{layer:'base',reused:true},{layer:'outer',reused:true},{layer:'accessory',reused:false}]));
 it('does not reuse base after changing tucked styling',()=>expect(reusedLayers(state,{...state,base:{mode:'top_bottom',top_id:'top',bottom_id:'bottom',tucked:true}})[0].reused).toBe(false));
});
