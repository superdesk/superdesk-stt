import {groupBy} from 'lodash';

const getCoverageScore = (item) => {
    const allCoverages = item.coverages ?? [];
    const textCoverages = allCoverages.filter(c => c.planning?.g2_content_type === 'text');

    if (textCoverages.length < 1) {
        return -1;
    }

    const coveragesByStatus = groupBy(allCoverages, (c) => c.news_coverage_status.qcode);

    const hasPlanned = (coveragesByStatus['ncostat:int'] ?? []).length > 0;
    const hasCompleted = allCoverages.some((c) => c.assigned_to?.state === 'completed');

    // move down coverages that have been completed, but news_coverage_status is still set to planned
    if (hasPlanned && !hasCompleted) {
        return 4;
    }

    if (hasCompleted) {
        return 3;
    }

    const hasMaybe = (coveragesByStatus['ncostat:notdec'] ?? []).length > 0;

    if (hasMaybe) {
        return 2;
    }

    const hasNotPlanned = (coveragesByStatus['ncostat:notint'] ?? []).length > 0;

    if (hasNotPlanned) {
        return 1;
    }

    return 0;
};

export const comparePlanningItems = (a, b) => {
    const aDepartment = (
        a.anpa_category?.[0]?.name ?? ""
    ).toLowerCase();
    const bDepartment = (
        b.anpa_category?.[0]?.name ?? ""
    ).toLowerCase();
    const departmentResult = aDepartment.localeCompare(bDepartment);

    if (departmentResult !== 0) {
        return departmentResult;
    }

    const aCoverageScore = getCoverageScore(a);
    const bCoverageScore = getCoverageScore(b);

    if (aCoverageScore !== bCoverageScore) {
        return bCoverageScore - aCoverageScore;
    }

    const aPriority = a.priority ?? 5; // 5 is lowest
    const bPriority = b.priority ?? 5;

    if (aPriority !== bPriority) {
        return aPriority - bPriority;
    }

    const aDate = a._updated || a._created || "";
    const bDate = b._updated || b._created || "";

    return bDate.localeCompare(aDate);
};
