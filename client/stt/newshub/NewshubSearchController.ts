import _ from "lodash";

interface Subject {
  id?: string;
  name: string;
  qcode?: string;
}

const META_VALUES_TO_CVS = [
  "sttdepartment",
  "sttgenre",
  "sttsubj",
  "stturgency",
];

export default class NewshubSearchController {
  periods: Subject[];
  subjects: Subject[];
  departments: Subject[];
  urgencies: Subject[];
  genres: Subject[];
  cvs: any[];
  desks: any;
  content: any;
  metadata: any;
  preferencesService: any;
  $location: any;
  $scope: any;
  $rootScope: any;
  vocabularies: any;
  api: any;
  params: any;

  static $inject: string[] = [
    "$scope",
    "$rootScope",
    "vocabularies",
    "api",
    "desks",
    "content",
    "metadata",
    "preferencesService",
  ];
  constructor(
    $scope,
    $rootScope,
    vocabularies,
    api,
    desks,
    content,
    metadata,
    preferencesService
  ) {
    this.$scope = $scope;
    this.$rootScope = $rootScope;
    this.vocabularies = vocabularies;
    this.api = api;
    this.desks = desks;
    this.content = content;
    this.metadata = metadata;
    this.preferencesService = preferencesService;
    this.params = {};

    // Initialize static lists
    this.periods = [
      { name: "Whenever", id: "" },
      { name: "Last 24 hours", id: "day" },
      { name: "Last week", id: "week" },
      { name: "Last month", id: "month" },
      { name: "Last year", id: "year" },
    ];
    desks.initialize();
    // Call the async initialization (fire-and-forget)
    this.initialize();

    metadata
      .initialize()
      .then(() => {
        $scope.metadata = metadata.values;
        console.log("metadata.values", metadata.values);
        return preferencesService.get();
      })
      .then(this.setAvailableSttDepartments.bind(this))
      .catch((error) => {
        console.error("Error initializing metadata:", error);
      });

    // $scope.$watch(
    //   () => this.params["sttsubj"],
    //   (newVal, oldVal) => {
    //     if (angular.isObject(newVal) && newVal.qcode) {
    //       this.params["sttsubj"] = newVal.qcode;
    //     }
    //   }
    // );

    // $scope.$watch(
    //   () => this.params["sttdepartment"],
    //   (newVal, oldVal) => {
    //     console.log("sttdepartment newVal", newVal);
    //     if (angular.isObject(newVal) && newVal.qcode) {
    //       this.params["sttdepartment"] = newVal.qcode;
    //     }
    //   }
    // );

    // $scope.$watch(
    //   () => this.params["sttgenre"],
    //   (newVal, oldVal) => {
    //     if (angular.isObject(newVal) && newVal.qcode) {
    //       this.params["sttgenre"] = newVal.qcode;
    //     }
    //   }
    // );

    // $scope.$watch(
    //   () => this.params["stturgency"],
    //   (newVal, oldVal) => {
    //     if (angular.isObject(newVal) && newVal.qcode) {
    //       this.params["stturgency"] = newVal.qcode;
    //     }
    //   }
    // );

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
  /**
   * Builds a list of categories available for selection in scope. Used by
   * the "category" menu in the Authoring metadata section.
   *
   * @function setAvailableCategories
   * @param {Object} prefs - user preferences setting, including the
   *   preferred categories settings, among other things
   */
  private setAvailableSttDepartments(prefs) {
    var all, // all available categories
      filtered,
      // user's department preference settings , i.e. a map
      // object (<department_code> --> true/false)
      userPrefs;

    all = this.metadata.values.sttdepartment || [];
    console.log("prefs: ", prefs);
    // userPrefs = prefs["sttdepartment:preferred"].selected;
    filtered = _.filter(
      all,
      (dept) => _.isEmpty(userPrefs) || userPrefs[dept.qcode]
    );
    this.$scope.availableDepartments = _.sortBy(filtered, "name");
    console.log(
      "this.$scope.availableDepartments",
      this.$scope.availableDepartments
    );
  }
  /**
   * Builds a list of company_codes available for selection in scope. Used by
   * the "company_codes" menu in the Authoring metadata section.
   *
   * @function setAvailableCompanyCodes
   */
  // private setAvailableCompanyCodes() {
  //   var all, // all available company codes
  //     assigned = {}, // company codes already assigned to the article
  //     filtered,
  //     itemCompanyCodes; // existing company codes assigned to the article

  //   all = _.cloneDeep(this.metadata.values.company_codes || []);

  //   all.forEach((companyCode) => {
  //     companyCode.name = companyCode.name + " (" + companyCode.qcode + ")";
  //   });

  //   // gather article's existing company codes
  //   itemCompanyCodes = this.$scope.item.company_codes || [];

  //   itemCompanyCodes.forEach((companyCode) => {
  //     assigned[companyCode.qcode] = true;
  //   });

  //   filtered = _.filter(all, (companyCode) => !assigned[companyCode.qcode]);

  //   this.$scope.availableCompanyCodes = _.sortBy(filtered, "name");
  // }
  private async initialize(): Promise<void> {
    try {
      const data = await this.vocabularies.getAllActiveVocabularies();
      this.cvs = data.filter((cv) => META_VALUES_TO_CVS.includes(cv._id));
      console.log("this.cvs", this.cvs);
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
  "$rootScope",
  "vocabularies",
  "api",
  "desks",
  "content",
  "metadata",
  "preferencesService",
];
