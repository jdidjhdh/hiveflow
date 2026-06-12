import type { Node, Edge } from 'reactflow';
import type { WorkflowNodeData } from '@/types';

export const templateData: Record<string, { nodes: Node<WorkflowNodeData>[]; edges: Edge[] }> = {
  rag_pipeline: {
    nodes: [
      { id: 'retrieve', type: 'taskNode', position: { x: 50, y: 100 }, data: { label: '文档检索', task: 'document_retrieval', skills: ['search', 'embedding'], variant: 'task', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'retrieved_docs', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'rerank', type: 'taskNode', position: { x: 270, y: 100 }, data: { label: '结果重排', task: 'result_reranking', skills: ['nlp', 'ranking'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'ranked_docs', expected_schema: {}, validation: '', deadline: 20, use_json_schema: false } } },
      { id: 'generate', type: 'taskNode', position: { x: 490, y: 100 }, data: { label: '生成回答', task: 'answer_generation', skills: ['llm', 'summarization'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'abort', expectation: { state_key: 'final_answer', expected_schema: {}, validation: '', deadline: 60, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-retrieve-rerank', source: 'retrieve', target: 'rerank', type: 'deletable' },
      { id: 'e-rerank-generate', source: 'rerank', target: 'generate', type: 'deletable' },
    ],
  },
  debate_decision: {
    nodes: [
      { id: 'issue', type: 'taskNode', position: { x: 250, y: 20 }, data: { label: '问题拆解', task: 'issue_decomposition', skills: ['planning', 'analysis'], variant: 'task', status: 'idle', on_failure: 'abort', expectation: { state_key: 'decomposed_issue', expected_schema: {}, validation: '', deadline: 15, use_json_schema: false } } },
      { id: 'analyst_a', type: 'taskNode', position: { x: 50, y: 140 }, data: { label: '分析师 A (乐观)', task: 'optimistic_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_a', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'analyst_b', type: 'taskNode', position: { x: 250, y: 140 }, data: { label: '分析师 B (悲观)', task: 'pessimistic_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_b', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'analyst_c', type: 'taskNode', position: { x: 450, y: 140 }, data: { label: '分析师 C (中立)', task: 'neutral_analysis', skills: ['analysis', 'reasoning'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'skip', expectation: { state_key: 'opinion_c', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
      { id: 'summary', type: 'taskNode', position: { x: 250, y: 270 }, data: { label: '汇总结论', task: 'conclusion_synthesis', skills: ['summarization', 'decision'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'abort', expectation: { state_key: 'final_decision', expected_schema: {}, validation: '', deadline: 45, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-issue-a', source: 'issue', target: 'analyst_a', type: 'deletable' },
      { id: 'e-issue-b', source: 'issue', target: 'analyst_b', type: 'deletable' },
      { id: 'e-issue-c', source: 'issue', target: 'analyst_c', type: 'deletable' },
      { id: 'e-a-summary', source: 'analyst_a', target: 'summary', type: 'deletable' },
      { id: 'e-b-summary', source: 'analyst_b', target: 'summary', type: 'deletable' },
      { id: 'e-c-summary', source: 'analyst_c', target: 'summary', type: 'deletable' },
    ],
  },
  hierarchical_planning: {
    nodes: [
      { id: 'planner', type: 'taskNode', position: { x: 250, y: 20 }, data: { label: '任务规划', task: 'task_planning', skills: ['planning', 'decomposition'], variant: 'task', status: 'idle', on_failure: 'abort', expectation: { state_key: 'task_plan', expected_schema: {}, validation: '', deadline: 20, use_json_schema: false } } },
      { id: 'exec_1', type: 'taskNode', position: { x: 50, y: 150 }, data: { label: '执行 Agent 1 (数据采集)', task: 'data_collection', skills: ['crawling', 'data_processing'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 3, backoff_type: 'exponential', backoff_base: 1, max_backoff: 30 }, on_failure: 'skip', expectation: { state_key: 'collected_data', expected_schema: {}, validation: '', deadline: 60, use_json_schema: false } } },
      { id: 'exec_2', type: 'taskNode', position: { x: 250, y: 150 }, data: { label: '执行 Agent 2 (模型训练)', task: 'model_training', skills: ['ml', 'training'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'exponential', backoff_base: 2, max_backoff: 60 }, on_failure: 'abort', expectation: { state_key: 'trained_model', expected_schema: {}, validation: '', deadline: 300, use_json_schema: false } } },
      { id: 'exec_3', type: 'taskNode', position: { x: 450, y: 150 }, data: { label: '执行 Agent 3 (特征工程)', task: 'feature_engineering', skills: ['data_analysis', 'preprocessing'], variant: 'dynamic', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 15 }, on_failure: 'skip', expectation: { state_key: 'features', expected_schema: {}, validation: '', deadline: 45, use_json_schema: false } } },
      { id: 'validator', type: 'taskNode', position: { x: 250, y: 280 }, data: { label: '结果验证', task: 'result_validation', skills: ['testing', 'evaluation'], variant: 'subgraph', status: 'idle', retry_policy: { max_attempts: 2, backoff_type: 'constant', backoff_base: 1, max_backoff: 10 }, on_failure: 'abort', expectation: { state_key: 'validation_report', expected_schema: {}, validation: '', deadline: 30, use_json_schema: false } } },
    ],
    edges: [
      { id: 'e-planner-exec1', source: 'planner', target: 'exec_1', type: 'deletable' },
      { id: 'e-planner-exec2', source: 'planner', target: 'exec_2', type: 'deletable' },
      { id: 'e-planner-exec3', source: 'planner', target: 'exec_3', type: 'deletable' },
      { id: 'e-exec1-validator', source: 'exec_1', target: 'validator', type: 'deletable' },
      { id: 'e-exec2-validator', source: 'exec_2', target: 'validator', type: 'deletable' },
      { id: 'e-exec3-validator', source: 'exec_3', target: 'validator', type: 'deletable' },
    ],
  },
  e2e_sandbox: {
    nodes: [
      {
        id: 'e2e_code',
        type: 'taskNode',
        position: { x: 120, y: 120 },
        data: {
          label: 'E2E Code',
          task: 'e2e_code',
          skills: [],
          variant: 'code',
          status: 'idle',
          code_data: {
            language: 'javascript',
            code: 'return { result: 0 };',
            input_mapping: {},
            output_mapping: {},
          },
        } as WorkflowNodeData,
      },
      {
        id: 'e2e_condition',
        type: 'taskNode',
        position: { x: 360, y: 120 },
        data: {
          label: 'E2E Condition',
          task: 'e2e_condition',
          skills: [],
          variant: 'condition',
          status: 'idle',
          condition_data: {
            condition: '',
            branches: [
              { id: 'true', label: 'Yes', condition: '' },
              { id: 'false', label: 'No', condition: '' },
            ],
            default_branch: 'false',
          },
        } as WorkflowNodeData,
      },
    ],
    edges: [],
  },
};
