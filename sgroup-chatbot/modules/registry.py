from modules.module_a import ModuleAAgent
from modules.module_b import ModuleBAgent

# Register practical modules used in current chatbot scope.
MODULE_REGISTRY: dict = {
    "module_a": ModuleAAgent,
    "module_b": ModuleBAgent,
}
