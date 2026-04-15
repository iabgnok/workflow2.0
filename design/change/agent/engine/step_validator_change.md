# step_validator.py 重构实现细节

## 一、这个文件的现状与命运

- 当前 StepValidator 是一个纯转发层：两个 classmethod，各自捕获 ProtocolRuntimeValidationError 再重新包装成 StepValidationError 抛出。逻辑本身在 protocol/runtime_assertions.py 里，这里只是换了异常类型。

- 重构结论：这个文件应该被吸收进 StepExecutor 里，不再作为独立文件存在。
    理由：StepValidator 只有两个方法，没有任何状态，没有任何依赖注入点，它存在的唯一价值是隔离异常类型。重构后 StepExecutor 直接调用 protocol.runtime_assertions.validate_step_inputs/outputs，自己处理 ProtocolRuntimeValidationError，不再需要这个中间层。

- StepValidationError 这个异常类型可以保留，定义在 engine/errors.py（新建，用于收集引擎层自定义异常）或直接用 ProtocolRuntimeValidationError，二者选其一即可。[待定：是否新建 engine/errors.py 统一管理引擎层异常类型，还是直接使用 protocol 层的异常]