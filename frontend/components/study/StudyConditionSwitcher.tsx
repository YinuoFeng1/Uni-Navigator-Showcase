import { Label, Select } from "@/components/ui/form";
import { studyConditionLabels } from "@/lib/constants";
import type { StudyCondition } from "@/lib/types";

type StudyConditionSwitcherProps = {
  value: StudyCondition;
  onChange: (condition: StudyCondition) => void;
  label?: string;
  disabled?: boolean;
};

export function StudyConditionSwitcher({
  value,
  onChange,
  label = "Evidence display condition",
  disabled = false,
}: StudyConditionSwitcherProps) {
  return (
    <div className="grid gap-2">
      <Label htmlFor="study-condition">{label}</Label>
      <Select
        id="study-condition"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as StudyCondition)}
      >
        {Object.entries(studyConditionLabels).map(([key, text]) => (
          <option key={key} value={key}>
            {text}
          </option>
        ))}
      </Select>
    </div>
  );
}
