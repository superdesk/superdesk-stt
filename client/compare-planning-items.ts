import {groupBy} from 'lodash';

const getCoverageScore = (item) => {
    if ((item.coverages ?? []).length < 1) {
        return -1;
    }

    const coverages = groupBy(item.coverages, (c) => c.news_coverage_status.qcode);

    const hasPlanned = (coverages['ncostat:int'] ?? []).length > 0;

    if (hasPlanned) {
        return 4;
    }

    const hasCompleted = (item.coverages ?? []).some((c) => c.assigned_to?.state === 'completed');

    if (hasCompleted) {
        return 3;
    }

    const hasMaybe = (coverages['ncostat:notdec'] ?? []).length > 0;

    if (hasMaybe) {
        return 2;
    }

    const hasNotPlanned = (coverages['ncostat:notint'] ?? []).length > 0;

    if (hasNotPlanned) {
        return 1;
    }

    return 0;
};

export const comparePlanningItem = (a, b) => {
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

    const aImportance = a.urgency ?? 5; // 5 is lowest
    const bImportance = b.urgency ?? 5;

    if (aImportance !== bImportance) {
        return aImportance - bImportance;
    }

    const aDate = a._updated || a._created || "";
    const bDate = b._updated || b._created || "";

    return bDate.localeCompare(aDate);
};
