interface Subject {
  id?: string;
  name: string;
  qcode?: string;
}

export default class NewshubSearchController {
  periods: Subject[];
  categories: any;
  genre: any;
  urgency: any;
  sttversions: any;
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
    '$scope',
    '$rootScope',
    'vocabularies',
    'api',
    'desks',
    'content',
    'metadata',
    'preferencesService',
  ];
  constructor(
    $scope: any,
    $rootScope: any,
    vocabularies: any,
    api: any,
    desks: any,
    content: any,
    metadata: any,
    preferencesService: any,
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

    this.$scope.params = this.$scope.params || {};
    this.$scope.params.dates = this.$scope.params.dates || {};

    // Initialize static lists
    this.periods = [
      { name: 'Whenever', id: '' },
      { name: 'Last 24 hours', id: 'day' },
      { name: 'Last week', id: 'week' },
      { name: 'Last month', id: 'month' },
      { name: 'Last year', id: 'year' },
    ];
    desks.initialize();
    // Call the async initialization (fire-and-forget)
    this.initialize();
  }

  private async initialize(): Promise<void> {
    try {
      const data = await this.vocabularies.getAllActiveVocabularies();

      this.categories = this.getVocabulary(data, 'categories');
      this.genre = this.getVocabulary(data, 'genre');
      this.urgency = this.getVocabulary(data, 'urgency');
      this.sttversions = this.getVocabulary(data, 'sttversion');
    } catch (error) {
      console.error('Failed to initialize vocabularies: ', error);
    }
  }

  private getVocabulary(data: any[], vocabularyId: string): any {
    const vocabulary = data.find((item: any) => item._id === vocabularyId);

    return vocabulary || null;
  }
}
