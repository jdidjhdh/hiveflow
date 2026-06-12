export type PageLocales = {
  dashboard: {
    connecting: string;
    title: string;
    liveMode: string;
    stats: {
      totalIntents: string;
      successRate: string;
      activeAgents: string;
      totalLoad: string;
    };
    charts: {
      agentLoad: string;
      noAgentData: string;
      load: string;
      eventTrend: string;
      eventCount: string;
    };
    eventStream: string;
    noEvents: string;
  };
  variables: {
    demoBanner: string;
    title: string;
    subtitle: string;
    create: string;
    syntaxAlert: {
      title: string;
      intro: string;
      stringExample: string;
      numberExample: string;
      objectExample: string;
    };
    columns: {
      name: string;
      type: string;
      scope: string;
      value: string;
      description: string;
      actions: string;
    };
    scope: {
      global: string;
      local: string;
    };
    types: {
      string: string;
      number: string;
      boolean: string;
      object: string;
      array: string;
    };
    actions: {
      edit: string;
      delete: string;
    };
    messages: {
      invalidObjectJson: string;
      invalidArrayJson: string;
      updated: string;
      added: string;
      deleted: string;
    };
    confirmDelete: string;
    confirmDeleteDesc: string;
    totalCount: string;
    empty: string;
    modal: {
      editTitle: string;
      createTitle: string;
    };
    form: {
      name: string;
      nameRequired: string;
      namePattern: string;
      namePlaceholder: string;
      type: string;
      value: string;
      valueRequired: string;
      valuePlaceholder: string;
      scope: string;
      description: string;
      descriptionPlaceholder: string;
    };
  };
  triggers: {
    demoBanner: string;
    title: string;
    subtitle: string;
    create: string;
    types: {
      webhook: string;
      schedule: string;
      event: string;
    };
    typeCards: {
      webhook: { title: string; description: string };
      schedule: { title: string; description: string };
      event: { title: string; description: string };
    };
    columns: {
      name: string;
      type: string;
      config: string;
      webhookUrl: string;
      workflowId: string;
      status: string;
      actions: string;
    };
    status: {
      enabled: string;
      disabled: string;
    };
    switch: {
      on: string;
      off: string;
    };
    actions: {
      edit: string;
      delete: string;
    };
    messages: {
      invalidConfigJson: string;
      updated: string;
      added: string;
      deleted: string;
      webhookCopied: string;
    };
    confirmDelete: string;
    confirmDeleteDesc: string;
    totalCount: string;
    empty: string;
    modal: {
      editTitle: string;
      createTitle: string;
    };
    form: {
      name: string;
      namePlaceholder: string;
      type: string;
      typeWebhook: string;
      typeSchedule: string;
      typeEvent: string;
      workflowId: string;
      workflowIdPlaceholder: string;
      enabled: string;
      webhook: {
        alertTitle: string;
        alertDesc: string;
        method: string;
        path: string;
        pathPlaceholder: string;
        bodyMappingDivider: string;
        bodyMapping: string;
        bodyMappingPlaceholder: string;
      };
      schedule: {
        alertTitle: string;
        alertDesc: string;
        cron: string;
        cronPlaceholder: string;
        timezone: string;
      };
      event: {
        alertTitle: string;
        alertDesc: string;
        eventName: string;
        eventNamePlaceholder: string;
        filter: string;
        filterPlaceholder: string;
      };
    };
  };
  tracer: {
    demoBanner: string;
    intentList: string;
    searchPlaceholder: string;
    noTraceData: string;
    status: {
      completed: string;
      failed: string;
      inProgress: string;
    };
    auditLoaded: string;
    traceDetail: string;
    selectIntent: string;
    replayLink: string;
    selectFromList: string;
    auditTimeline: string;
  };
  replay: {
    realModeRequired: string;
    title: string;
    refresh: string;
    infoAlert: string;
    intentReplay: string;
    intentIdPlaceholder: string;
    query: string;
    sessionInfo: string;
    noAuditRecords: string;
    checkpointTimeline: string;
    workflowIdPlaceholder: string;
    load: string;
    noCheckpointHint: string;
    goToTracer: string;
  };
  events: {
    resume: string;
    pause: string;
    clear: string;
    filterByTopic: string;
    filterByAgent: string;
    count: string;
    liveMode: string;
    paused: string;
    noEvents: string;
  };
  blackboard: {
    keyList: string;
    searchKey: string;
    noData: string;
    valueTitle: string;
    selectKey: string;
    edit: string;
    selectKeyHint: string;
    permissions: string;
    readableAgents: string;
    writableAgents: string;
    none: string;
    auditLog: string;
    realAudit: string;
    mockAudit: string;
    totalRecords: string;
    columns: {
      time: string;
      action: string;
      agent: string;
      key: string;
    };
    editModal: string;
    messages: {
      valueUpdated: string;
      invalidJson: string;
    };
  };
  approvals: {
    realModeRequired: string;
    title: string;
    refresh: string;
    agentModeHint: string;
    empty: string;
    approve: string;
    reject: string;
    planTag: string;
    workflowNode: string;
    planPlaceholder: string;
    commentPlaceholder: string;
    messages: {
      approved: string;
      rejected: string;
      invalidPlanJson: string;
      planMustBeObject: string;
      planMustHaveFinalAnswer: string;
    };
  };
  settings: {
    title: string;
    connectionError: string;
    agentRuntime: {
      title: string;
      hint: string;
      mode: string;
      agent: string;
      core: string;
      realModeRequired: string;
      query: string;
      queryPlaceholder: string;
      runQuery: string;
      queryComplete: string;
    };
    scheduling: {
      title: string;
      strategy: string;
      leastLoaded: string;
      auction: string;
      auctionTimeout: string;
    };
    mock: {
      title: string;
      delayRange: string;
      min: string;
      max: string;
      failProbability: string;
    };
    other: {
      title: string;
      notPersistedTitle: string;
      notPersistedDesc: string;
      defaultTimeout: string;
      maxAuditEntries: string;
      encryptedBlackboard: string;
      encryptedHint: string;
    };
    save: string;
    saved: string;
    runtimeSwitched: string;
  };
  analytics: {
    demoBanner: string;
    loading: string;
    noData: string;
    title: string;
    timeRange: string;
    last7Days: string;
    last30Days: string;
    stats: {
      totalExecutions: string;
      successRate: string;
      avgDuration: string;
      failedCount: string;
    };
    charts: {
      executionTrend: string;
      nodeRanking: string;
      nodeRankingTooltip: string;
      agentLoad: string;
      errorStats: string;
      recentExecutions: string;
    };
    trend: {
      executions: string;
      success: string;
      failed: string;
      avgDuration: string;
      countAxis: string;
      durationAxis: string;
    };
    nodeRanking: {
      rank: string;
      nodeName: string;
      callCount: string;
      avgDuration: string;
      maxDuration: string;
      minDuration: string;
      distribution: string;
    };
    agentLoad: {
      executionCount: string;
    };
    errorStats: {
      noData: string;
      tooltip: string;
      totalErrors: string;
    };
    executions: {
      id: string;
      workflow: string;
      status: string;
      duration: string;
      nodeCount: string;
      time: string;
      success: string;
      failed: string;
      timeout: string;
    };
  };
  auditLog: {
    title: string;
    subtitle: string;
    export: string;
    refresh: string;
    stats: {
      total: string;
      read: string;
      write: string;
      wait: string;
      activeAgents: string;
      permissionDenied: string;
    };
    permissionAlert: {
      title: string;
      description: string;
    };
    filters: {
      title: string;
      searchPlaceholder: string;
      allAgents: string;
      allKeys: string;
      allActions: string;
    };
    actions: {
      get: string;
      put: string;
      wait: string;
      sysGet: string;
      sysWait: string;
      sysPut: string;
      sysDelete: string;
    };
    agentActivity: string;
    agentActivityCount: string;
    records: string;
    columns: {
      time: string;
      action: string;
      agent: string;
      key: string;
      status: string;
      details: string;
    };
    status: {
      denied: string;
      success: string;
    };
    timeline: {
      title: string;
      operated: string;
    };
    totalRecords: string;
  };
  agents: {
    title: string;
    searchPlaceholder: string;
    tableView: string;
    cardView: string;
    batchDrain: string;
    batchStop: string;
    batchActions: string;
    create: string;
    hiveMindSkills: string;
    agentMode: string;
    empty: string;
    registerFirst: string;
    columns: {
      agentId: string;
      displayName: string;
      skills: string;
      status: string;
      load: string;
      queue: string;
      weight: string;
      actions: string;
    };
    actions: {
      detail: string;
      drain: string;
      unregister: string;
      delete: string;
    };
    card: {
      detail: string;
      drain: string;
    };
    confirmDelete: string;
    totalCount: string;
    messages: {
      batchDrained: string;
      batchStopped: string;
      deleted: string;
      updated: string;
      registered: string;
    };
  };
  capabilityMarket: {
    title: string;
    tabs: {
      marketplace: string;
      myCapabilities: string;
    };
    marketplace: {
      demoBanner: string;
      totalPlugins: string;
      searchPlaceholder: string;
      allCategories: string;
      refresh: string;
      totalCount: string;
      columns: {
        name: string;
        category: string;
        description: string;
        tags: string;
        status: string;
        actions: string;
      };
      status: {
        installed: string;
        notInstalled: string;
      };
      install: string;
      messages: {
        mockInstallWarning: string;
        installedWithSkills: string;
        installed: string;
        enableAgentMode: string;
        noSkillsRegistered: string;
      };
      skillModal: {
        title: string;
        description: string;
      };
    };
    myCapabilities: {
      create: string;
      exportAll: string;
      import: string;
      allTypes: string;
      searchPlaceholder: string;
      stats: {
        total: string;
        externalService: string;
        preset: string;
        onlineEdit: string;
      };
      totalCount: string;
      columns: {
        name: string;
        type: string;
        createdAt: string;
        agentCount: string;
        description: string;
        actions: string;
      };
      source: {
        preset: string;
        externalService: string;
        upload: string;
        onlineEdit: string;
      };
      actions: {
        edit: string;
        export: string;
        delete: string;
      };
      confirmDelete: string;
      modal: {
        editTitle: string;
        createTitle: string;
        save: string;
        cancel: string;
      };
      form: {
        name: string;
        namePlaceholder: string;
        description: string;
        descriptionPlaceholder: string;
        type: string;
        externalConfig: string;
        url: string;
        urlPlaceholder: string;
        method: string;
        headers: string;
        headersPlaceholder: string;
        body: string;
        bodyPlaceholder: string;
        outputMapping: string;
        storageKey: string;
        timeout: string;
        codeEditor: string;
        code: string;
        codePlaceholder: string;
      };
      messages: {
        updated: string;
        created: string;
        deleted: string;
        exported: string;
        imported: string;
        importFailed: string;
      };
    };
  };
  knowledgeBase: {
    title: string;
    searchPlaceholder: string;
    create: string;
    empty: string;
    emptySearch: string;
    createFirst: string;
    modal: {
      editTitle: string;
      createTitle: string;
    };
    form: {
      name: string;
      nameRequired: string;
      namePlaceholder: string;
      description: string;
      descriptionPlaceholder: string;
      embeddingModel: string;
    };
    card: {
      edit: string;
      delete: string;
      confirmDelete: string;
      noDescription: string;
      docCount: string;
      processing: string;
      chunkInfo: string;
    };
    detail: {
      backToList: string;
      tabs: {
        documents: string;
        chunking: string;
        search: string;
      };
      upload: {
        hint: string;
        formats: string;
      };
      startEmbedding: string;
      embeddingModel: string;
      columns: {
        fileName: string;
        type: string;
        size: string;
        status: string;
        chunks: string;
        actions: string;
      };
      docStatus: {
        pending: string;
        processing: string;
        completed: string;
        failed: string;
      };
      confirmDeleteDoc: string;
      delete: string;
      noDocuments: string;
      chunk: {
        size: string;
        overlap: string;
        hintTitle: string;
        hintDesc: string;
        save: string;
      };
      search: {
        placeholder: string;
        search: string;
        results: string;
        similarity: string;
        noResults: string;
        startHint: string;
        enterContent: string;
      };
    };
    messages: {
      unsupportedFileType: string;
      fileUploaded: string;
      embeddingStarted: string;
      enterSearchContent: string;
      chunkConfigSaved: string;
      deleted: string;
      updated: string;
      created: string;
    };
  };
  llmConfig: {
    title: string;
    subtitle: string;
    tabs: {
      providers: string;
      credentials: string;
    };
    providerMeta: {
      custom: string;
    };
    presetModels: string;
    columns: {
      name: string;
      provider: string;
      model: string;
      temperature: string;
      maxTokens: string;
      baseUrl: string;
      actions: string;
    };
    credColumns: {
      id: string;
      name: string;
      type: string;
      createdAt: string;
      actions: string;
    };
    actions: {
      test: string;
      edit: string;
      delete: string;
      createCredential: string;
    };
    securityAlert: {
      title: string;
      description: string;
    };
    confirmDelete: string;
    confirmDeleteDesc: string;
    confirmDeleteCredential: string;
    modal: {
      editProvider: string;
      createProvider: string;
      createCredential: string;
    };
    form: {
      configName: string;
      configNamePlaceholder: string;
      provider: string;
      modelName: string;
      modelNamePlaceholder: string;
      baseUrl: string;
      apiKeyCredential: string;
      selectCredential: string;
      newCredential: string;
      credentialName: string;
      credentialNamePlaceholder: string;
      credentialType: string;
      credentialValue: string;
      credentialValuePlaceholder: string;
      types: {
        apiKey: string;
        oauth: string;
        basicAuth: string;
        custom: string;
      };
    };
    messages: {
      providerUpdated: string;
      providerAdded: string;
      providerDeleted: string;
      testFailed: string;
      credentialCreated: string;
      credentialDeleted: string;
      deleteCredentialFailed: string;
    };
  };
  promptTemplates: {
    title: string;
    subtitle: string;
    create: string;
    seed: string;
    searchPlaceholder: string;
    allCategories: string;
    columns: {
      name: string;
      category: string;
      description: string;
      tags: string;
      variables: string;
      version: string;
      actions: string;
    };
    categories: {
      general: string;
      chat: string;
      rag: string;
      agent: string;
      tool: string;
    };
    tooltips: {
      edit: string;
      versions: string;
      test: string;
      compare: string;
      copy: string;
      delete: string;
    };
    confirmDelete: string;
    modal: {
      editTitle: string;
      createTitle: string;
      save: string;
      cancel: string;
    };
    form: {
      name: string;
      namePlaceholder: string;
      category: string;
      content: string;
      contentPlaceholder: string;
      description: string;
      descriptionPlaceholder: string;
      tags: string;
      tagsPlaceholder: string;
      variables: string;
      variablesPlaceholder: string;
      modelHints: string;
      modelHintsPlaceholder: string;
    };
    versionDrawer: {
      title: string;
      noVersions: string;
      currentVersion: string;
      noChangeSummary: string;
      characters: string;
      rollback: string;
      confirmRollback: string;
    };
    testDrawer: {
      title: string;
      variableAssignment: string;
      inputValue: string;
      runTest: string;
      results: string;
      version: string;
      charCount: string;
      tokenEstimate: string;
      unreplacedVariables: string;
      none: string;
      rendered: string;
    };
    compareDrawer: {
      title: string;
      versionA: string;
      versionB: string;
      compare: string;
      addedLines: string;
      removedLines: string;
      similarity: string;
      diff: string;
    };
    messages: {
      updated: string;
      created: string;
      deleted: string;
      rolledBack: string;
      seeded: string;
      copied: string;
    };
    copySuffix: string;
  };
  abTesting: {
    title: string;
    subtitle: string;
    create: string;
    stats: {
      total: string;
      completed: string;
      aWins: string;
      bWins: string;
    };
    columns: {
      name: string;
      configA: string;
      configB: string;
      criteria: string;
      result: string;
      status: string;
      actions: string;
    };
    config: {
      model: string;
      temperature: string;
    };
    result: {
      notRun: string;
      aWins: string;
      bWins: string;
      tie: string;
    };
    status: {
      draft: string;
      running: string;
      completed: string;
      failed: string;
    };
    actions: {
      run: string;
      viewResults: string;
      delete: string;
    };
    modal: {
      title: string;
      create: string;
      cancel: string;
    };
    form: {
      name: string;
      namePlaceholder: string;
      description: string;
      descriptionPlaceholder: string;
      configA: string;
      configB: string;
      model: string;
      temperature: string;
      tools: string;
      toolsPlaceholder: string;
      criteria: string;
      criteriaHelp: string;
      criteriaPlaceholder: string;
    };
    messages: {
      created: string;
      createFailed: string;
      running: string;
      completed: string;
      deleted: string;
    };
    results: {
      drawerTitle: string;
      tie: string;
      winner: string;
      scoreSummary: string;
      scoreComparison: string;
      config: string;
      model: string;
      temperature: string;
      overallScore: string;
      latency: string;
      criteriaDetails: string;
      outputComparison: string;
      close: string;
      columns: {
        criterion: string;
        scoreA: string;
        scoreB: string;
        winner: string;
        reasonA: string;
        reasonB: string;
      };
      tieTag: string;
      reasonTemplate: string;
      performance: {
        excellent: string;
        good: string;
        fair: string;
      };
    };
  };
};
