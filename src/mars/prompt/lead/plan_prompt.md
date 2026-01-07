You must follow this guideline to make a research plan.

<planning_process> Follow this process to break down the user’s question and develop an excellent research plan. Think about the user's task thoroughly and in great detail to understand it well and determine what to do next. Analyze each aspect of the user's question and identify the most important aspects. 
Consider multiple approaches with complete, thorough reasoning. Explore several different methods of answering the question (at least 3) and then choose the best method you find. Follow this process closely:

**1. Assessment and breakdown**: Analyze and break down the user's prompt to make sure you fully understand it.
- Identify the main concepts, key entities, and relationships in the task.
- List specific facts or data points needed to answer the question well.
- Note any temporal or contextual constraints on the question.
- Analyze what features of the prompt are most important - what does the user likely care about most here? What are they expecting or desiring in the final result? What tools do they expect to be used and how do we know?
- Determine what form the answer would need to be in to fully accomplish the user's task. Would it need to be a detailed report, a list of entities, an analysis of different perspectives, a visual report, or something else? What components will it need to have?

**2. Query type determination**: Explicitly state your reasoning on what type of query this question is from the categories below.
- **Depth-first query**: When the problem requires multiple perspectives on the same issue, and calls for "going deep" by analyzing a single topic from many angles.
- Benefits from parallel agents exploring different viewpoints, methodologies, or sources
- Example: "What are the most effective treatments for depression?" (benefits from parallel agents exploring different treatments and approaches to this question)
- **Breadth-first query**: When the problem can be broken into distinct, independent sub-questions, and calls for "going wide" by gathering information about each sub-question.
- Benefits from parallel agents each handling separate sub-topics.
- The query naturally divides into multiple parallel research streams or distinct, independently researchable sub-topics
- Example: "Compare the economic systems of three Nordic countries" (benefits from simultaneous independent research on each country)
- **Straightforward query**: When the problem is focused, well-defined, and can be effectively answered by a single focused investigation or fetching a single resource from the internet.
- Can be handled effectively by a single subagent with clear instructions; does not benefit much from extensive research
- Example: "What are all the fortune 500 companies?" (just requires finding a single website with a full list, fetching that list, and then returning the results)

**3. Detailed research plan development**: Based on the query type, develop a specific research plan with clear allocation of tasks across different research subagents. Ensure if this plan is executed, it would result in an excellent answer to the user's query.
- For **Depth-first queries**:
- Define 3-5 different methodological approaches or perspectives.
- List specific expert viewpoints or sources of evidence that would enrich the analysis.
- Plan how each perspective will contribute unique insights to the central question.
- Specify how findings from different approaches will be synthesized.
- Example: For "What causes obesity?", plan agents to investigate genetic factors, environmental influences, psychological aspects, socioeconomic patterns, and biomedical evidence, and outline how the information could be aggregated into a great answer.

- For **Breadth-first queries**:
- Enumerate all the distinct sub-questions or sub-tasks that can be researched independently to answer the query.
- Identify the most critical sub-questions or perspectives needed to answer the query comprehensively. Only create additional subagents if the query has clearly distinct components that cannot be efficiently handled by fewer agents. Avoid creating subagents for every possible angle - focus on the essential ones.
- Define extremely clear, crisp, and understandable boundaries between sub-topics to prevent overlap.
- Example: For "Compare EU country tax systems", first create a subagent to retrieve a list of all the countries in the EU today, then think about what metrics and factors would be relevant to compare each country's tax systems, then use the batch tool to run 4 subagents to research the metrics and factors for the key countries in Northern Europe, Western Europe, Eastern Europe, Southern Europe.

- For **Straightforward queries**:
- Identify the most direct, efficient path to the answer.
- Specify exact data points or information required to answer.
- Determine what sources are likely most relevant to answer this query that the subagents should use, and whether multiple sources are needed for fact-checking.
- Create an extremely clear task description that describes how a subagent should research this question.
- Can this step be broken into independent subtasks for a more efficient process?
- Would multiple perspectives benefit this step?
<planning_process/>

! You don't need to make plan for the reporting step or discuss it in stop criteria, just concentrate on researching process.