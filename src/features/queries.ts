import {queryOptions} from '@tanstack/react-query';
import {api} from '@/api/client';
export const itemsQuery=queryOptions({queryKey:['items'],queryFn:()=>api.items()});
export const bodiesQuery=queryOptions({queryKey:['bodies'],queryFn:api.bodies});
export const profileQuery=queryOptions({queryKey:['profile'],queryFn:api.profile});
export const backgroundsQuery=queryOptions({queryKey:['backgrounds'],queryFn:api.backgrounds});
export const outfitsQuery=queryOptions({queryKey:['outfits'],queryFn:api.outfits});
export const outfitQuery=(id:string)=>queryOptions({queryKey:['outfit',id],queryFn:()=>api.outfit(id)});
export const jobsQuery=(id:string)=>queryOptions({queryKey:['jobs',id],queryFn:()=>api.jobs(id),refetchInterval:q=>q.state.data?.some(j=>j.status==='running'||j.status==='queued')?1500:false});
