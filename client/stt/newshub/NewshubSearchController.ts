interface Subject {
  id?: string;
  name: string;
  qcode?: string;
}

export default class NewshubSearchController {
  periods: Subject[];
  subjects: Subject[];
  departments: Subject[];
  urgencies: Subject[];
  genres: Subject[];
  cvs: any[];
  $location: any;
  $scope: any;
  $rootScope: any;
  vocabularies: any;
  api: any;

  static $inject: string[] = [
    "$scope",
    "$location",
    "$rootScope",
    "vocabularies",
    "api",
  ];
  constructor($scope, $location, $rootScope, vocabularies, api) {
    this.$scope = $scope;
    this.$location = $location;
    this.$rootScope = $rootScope;
    this.vocabularies = vocabularies;
    this.api = api;

    // Initialize static lists
    this.periods = [
      { name: "Whenever", id: "" },
      { name: "Last 24 hours", id: "day" },
      { name: "Last week", id: "week" },
      { name: "Last month", id: "month" },
      { name: "Last year", id: "year" },
    ];
    // @ts-ignore
    window.vocabularies = this.vocabularies;
    // Call the async initialization (fire-and-forget)
    this.initialize();

    // Setup listeners (example shown)
    $rootScope.$on("vocabularies:created", (event, data) => {
      api.find("vocabularies", data.vocabulary_id).then((cv) => {
        this.cvs = this.cvs.concat([cv]);
      });
    });
    $rootScope.$on("vocabularies:updated", (event, data) => {
      api.find("vocabularies", data.vocabulary_id).then((cv) => {
        this.cvs = this.cvs.map((_cv) => (_cv._id === cv._id ? cv : _cv));
      });
    });
  }
  private async initialize(): Promise<void> {
    try {
      const data = await this.vocabularies.getAllActiveVocabularies();
      this.cvs = data;
      const subjects = data.filter((cv) => cv._id === "sttsubj");
      this.subjects = subjects.length > 0 ? subjects[0] : null;
      const departments = data.filter((cv) => cv._id === "sttdepartment");
      this.departments = departments.length > 0 ? departments[0] : null;
      const urgencies = data.filter((cv) => cv._id === "stturgency");
      this.urgencies = urgencies.length > 0 ? urgencies[0] : null;
      const genres = data.filter((cv) => cv._id === "sttgenre");
      this.genres = genres.length > 0 ? genres[0] : null;
      console.log(
        "Subjects, Departments, Urgencies, and Genres initialized successfully."
      );
      console.log("this.subjects", this.subjects);
      console.log("this.departments", this.departments);
      console.log("this.urgencies", this.urgencies);
      console.log("this.genres", this.genres);
    } catch (error) {
      console.error("Failed to initialize vocabularies: ", error);
    }
  }
}
NewshubSearchController.$inject = [
  "$scope",
  "$location",
  "$rootScope",
  "vocabularies",
  "api",
];
