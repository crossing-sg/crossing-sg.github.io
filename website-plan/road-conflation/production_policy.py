"""Final proposal eligibility; permission evidence and road function stay separate."""
from enrich_candidates import effective_access,POSITIVE,RESTRICTED,CAMPUS_NAMES
from refine_candidates import NON_ROADS,OUT_OF_SCOPE,VEHICULAR,value,numeric

AUTO='AUTO_ELIGIBLE'
REVIEW='REVIEW_REQUIRED'
NOT='NOT_AUTOMATICALLY_INCLUDED'
VERSION='proposal-roads-v1'


def eligibility(road_class,tags,linked,*,campus=False,connected=False,endpoint_links=0,
                match_kind='missing',match_reason='',boundary=False,grade_conflict=False,
                barrier_restriction=False,corridor_supported=False):
    """AUTO is reasonable proposal-road evidence, not certified public ownership.

    A named NUS connector may qualify on positive vehicular-role evidence despite
    missing permission tags. Missing tags are explicitly recorded as unknown.
    """
    highway=value(tags.get('highway')) if linked else value(road_class)
    subtype=value(tags.get('service')) if linked else ''
    motor,motor_basis=effective_access(tags,['motor_vehicle','vehicle','access'])
    foot,foot_basis=effective_access(tags,['foot','access'])
    evidence=dict(highway=highway,service=subtype or 'not_tagged',motor_access=motor,
                  motor_access_basis=motor_basis,foot_access=foot,foot_access_basis=foot_basis,
                  access_unknown=motor=='unknown',public_access_certified=False)
    if highway in NON_ROADS|OUT_OF_SCOPE:
        return NOT,'non_road_expressway_or_non_operational',evidence
    if subtype=='parking_aisle':return NOT,'identified_parking_aisle',evidence
    if subtype=='driveway' and (motor in RESTRICTED or motor=='unknown'):
        return NOT,'private_or_unverified_driveway_not_ordinary_proposal_road',evidence
    reasons=[]
    if not linked:reasons.append('OSM_identifier_or_geometry_not_verified')
    if linked and value(road_class)!=highway:reasons.append('source_highway_class_conflict')
    if motor in RESTRICTED:reasons.append('explicit_motor_access_'+motor)
    if foot in RESTRICTED:reasons.append('explicit_pedestrian_access_'+foot)
    if value(tags.get('access')) in RESTRICTED and motor in POSITIVE:reasons.append('conflicting_permission_tags')
    if subtype in {'driveway','drive-through','drive_through','emergency_access'}:reasons.append('special_service_access')
    if boundary:reasons.append('study_boundary_clipped')
    if grade_conflict:reasons.append('source_grade_disagreement')
    if barrier_restriction:reasons.append('associated_restricted_barrier')
    if any(value(tags.get(k)) not in {'','no','false','0'} for k in ['bridge','tunnel']) or numeric(tags.get('layer'))!=0:
        reasons.append('grade_separation_crossing_suitability')
    if match_kind=='uncertain':
        # A positive short connector is not rejected solely because it is under
        # the pilot's 10 m fragment rule. Other spatial uncertainty stays review.
        harmless={'no_corresponding_line','short_missing_fragment'}
        if not set(match_reason.split(';')).issubset(harmless):reasons.append('unresolved_spatial_match')
    if 'independent_parallel' in match_reason or 'displacement_or_parallel' in match_reason:
        reasons.append('parallel_or_displaced_representation')
    if not connected:reasons.append('no_reference_connected_vehicular_component')
    route=(numeric(tags.get('lanes'))>=1 and
           (numeric(tags.get('lanes'))>=2 or value(tags.get('sidewalk')) not in {'','no','none'} or any(k.startswith('turn:lanes') for k in tags)))
    if highway=='service':
        name=value(tags.get('name'))
        if any(clue in name for clue in ['car park','parking','condo','entrance','exit']):reasons.append('parking_or_development_access_context')
        if motor in POSITIVE and (route or name or subtype=='alley'):
            basis='positive_permission_and_vehicular_route'
        elif campus and name in CAMPUS_NAMES and (route or corridor_supported) and endpoint_links>=1:
            basis='named_NUS_connector_positive_route_or_continuous_corridor_evidence_access_unknown'
        else:
            basis='';reasons.append('service_function_or_permission_insufficient')
    elif highway in VEHICULAR:
        basis='vehicular_road_class_with_documented_access_unknown' if motor=='unknown' else 'vehicular_road_class_and_permission_evidence'
    else:
        basis='';reasons.append('road_class_requires_review')
    if reasons:return REVIEW,';'.join(sorted(set(reasons))),evidence
    return AUTO,basis,evidence
