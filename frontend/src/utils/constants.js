export const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
  { id: 'suspects', label: 'Suspect Queue', icon: 'checklist' },
  { id: 'pipeline', label: 'Pipeline Monitor', icon: 'monitoring' },
  { id: 'members', label: 'Members', icon: 'group' },
  { id: 'reviews', label: 'Reviews', icon: 'assignment_turned_in' },
];

export const REVIEW_DECISIONS = {
  SUPPORTED: {
    label: 'Supported',
    icon: 'check_circle',
    color: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    description: 'Documentation clearly supports HCC category in encounter records.',
  },
  NOT_SUPPORTED: {
    label: 'Not Supported',
    icon: 'cancel',
    color: 'bg-rose-100 text-rose-800 border-rose-300',
    description: 'Encounter records lack sufficient clinical documentation.',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence',
    icon: 'help',
    color: 'bg-amber-100 text-amber-800 border-amber-300',
    description: 'Additional medical records or physician query required.',
  },
};

export const GAP_TYPES = {
  EMERGING: {
    label: 'EMERGING',
    badgeTone: 'pink',
    desc: 'Newly documented condition in current claims; not present in historical baseline.',
  },
  RECAPTURE: {
    label: 'RECAPTURE',
    badgeTone: 'violet',
    desc: 'Documented chronic condition from historical baseline requiring re-documentation.',
  },
};
