from typing import TypedDict, List, Dict


class IOSpec(TypedDict):
    type: str  # "single_test_case" | "multi_test_case"


class SampleIO(TypedDict):
    input: str
    output: str


class AlgorithmProblem(TypedDict):
    id: str
    title: str
    desc: str
    constraints: str
    sample_io: List[SampleIO]
    io_spec: IOSpec
    std_solution: str
    tag: str
    brief_description: str
    source: str  # "local" | "llm_generated"


class MCQProblem(TypedDict):
    question_id: str
    tag: str
    text: str
    options: Dict[str, str]
    correct_options: List[str]
    explanation: str


class ProblemSet(TypedDict):
    exam_id: str
    exam_date: str
    target_tags: List[str]
    algorithm_section: List[AlgorithmProblem]
    mcq_section: List[MCQProblem]
