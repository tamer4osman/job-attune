import { emptyCategories, type JobProfile } from "@/lib/attune";

export const EMPTY_PROFILE: JobProfile = {
  profileName: "",
  company: { name: "", summary: "", valuesText: "" },
  job: { title: "", description: "" },
  categories: emptyCategories(),
};
