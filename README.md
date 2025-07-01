Discovery Phase
Purpose: Initial service discovery and capability negotiation
Process:
	•	Client sends a GET request to `/well-known/agent-card` endpoint
	•	Server responds with an Agent Card containing service capabilities and metadata
	•	This phase establishes what services and features are available
	•	Similar to service discovery where “the service client or consumer has to search the service registry in order to locate a service provider”
Key Characteristics:
	•	First contact between client and server
	•	Read-only operation (GET request)
	•	Provides service metadata and available capabilities
2. Initiation Phase
Purpose: Task creation and initial setup
Process:
	•	Client sends POST request to `/tasks/send` or `/tasks/sendSubscribe`
	•	Server processes the request and returns:
	•	Initial message confirmation
	•	Unique Task ID for tracking
	•	Establishes the foundation for task processing
Key Characteristics:
	•	Creates new task instance
	•	Generates unique identifier for the session
	•	Determines processing type (send vs. sendSubscribe)
3. Processing Phase
Purpose: Core task execution with flexible response handling
Two Processing Models:
Streaming Mode
	•	Uses Server-Sent Events (SSE) for real-time updates
	•	Provides continuous status updates and artifacts
	•	Ideal for long-running or complex tasks
	•	Real-time feedback to client
Non-Streaming Mode
	•	Returns Final Task Object upon completion
	•	Batch processing approach
	•	Suitable for quick, straightforward tasks
	•	Single response with complete results
Key Characteristics:
	•	Alternative execution paths (streaming vs. non-streaming)
	•	Flexible response handling based on task requirements
	•	Progress tracking capabilities
4. Interaction Phase (Optional)
Purpose: Handle dynamic user input and continued communication
When Activated:
	•	Triggered when Input Required from user
	•	Enables interactive task processing
	•	Supports multi-step workflows
Process:
	•	Client sends additional POST requests to `/tasks/send` or `/tasks/sendSubscribe`
	•	Subsequent messages exchange between client and server
	•	Allows for dynamic task modification or additional data input
Key Characteristics:
	•	Optional phase - not all tasks require interaction
	•	Bidirectional communication continues
	•	Enables complex workflows with user participation
5. Completion Phase
Purpose: Task finalization and status reporting
Process:
	•	Server sends Terminal State notification
	•	Three possible outcomes:
	•	Completed - Task finished successfully
	•	Failed - Task encountered errors
	•	Cancelled - Task was terminated by user/system
Key Characteristics:
	•	Final phase of the workflow
	•	Definitive status communication
	•	Resource cleanup and session termination
	•	Audit trail completion