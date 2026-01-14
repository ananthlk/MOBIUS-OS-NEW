# Mobius OS - Reusable Components List

Based on the UI mockup, here are all the sub-reusable modules/components we've created:

## Header Components

### 1. **ClientLogo** 
- **Purpose**: Displays client/customer logo and name
- **Props**: logoUrl, clientName
- **Location**: Top-left of header
- **Features**: Logo image + text name

### 2. **MobiusLogo**
- **Purpose**: Animated infinity symbol logo with status indication
- **Props**: status (idle | processing), size
- **States**: 
  - Idle: Static grey-to-white gradient
  - Processing: Animated gradient (grey ↔ white)
- **Features**: SVG infinity symbol, no rotation/spin

### 3. **StatusIndicator**
- **Purpose**: Visual status indicator (dot)
- **Props**: status (proceed | pending | error)
- **States**: Green (proceed), Orange (pending), Red (error)
- **Features**: Colored dot with glow effect

### 4. **ModeBadge**
- **Purpose**: Displays current browser/workflow mode
- **Props**: mode (Eligibility, Front Desk, Backend, Email Drafter, etc.)
- **Features**: Text badge, no background box

### 5. **AlertButton**
- **Purpose**: Shows live alerts/notifications
- **Props**: hasAlerts (boolean), onClick
- **States**: 
  - Normal: Transparent with dot icon
  - Has Alerts: Yellow background with red notification dot
- **Features**: Click to view alerts

### 6. **SettingsButton**
- **Purpose**: Opens settings panel
- **Props**: onClick
- **Features**: Gear icon button

## Context Components

### 7. **ContextDisplay**
- **Purpose**: Shows current extension context
- **Props**: context (read-only text), statusIndicator, modeBadge
- **Features**: System-generated, read-only display

### 8. **ContextSummary**
- **Purpose**: Summary of current context/work
- **Props**: summary (text)
- **Features**: Multi-line text display

### 9. **QuickActionButton**
- **Purpose**: Context-aware quick action button
- **Props**: label, onClick, actionType
- **Features**: Blue button, dynamically generated based on context

## Tasks & Reminders Components

### 10. **TasksPanel**
- **Purpose**: Collapsible panel for tasks and reminders
- **Props**: tasks (array), statusIndicator
- **Features**: 
  - Collapsible header
  - Status indicator (active/pending)
  - Task list display

### 11. **TaskItem**
- **Purpose**: Individual task/reminder item
- **Props**: 
  - id, label, checked, disabled
  - type (normal | shared | backend)
- **States**:
  - Normal: Regular task
  - Shared: Blue text (from backend)
  - Backend: Grey/italic (for backend to do)
- **Features**: Checkbox, label, styling based on type

## Chat Components

### 12. **ThinkingBox**
- **Purpose**: Collapsible system thinking/processing display
- **Props**: content (array of strings), isCollapsed
- **Features**: 
  - Collapsible header with arrow
  - Real-time progress display
  - Light grey background

### 13. **SystemMessage**
- **Purpose**: System/assistant message display
- **Props**: 
  - content (text)
  - thinkingBox (optional)
  - feedbackComponent (optional)
  - guidanceActions (optional)
- **Features**: 
  - Left-aligned
  - Light grey background
  - Contains thinking box, message, feedback, and guidance

### 14. **UserMessage**
- **Purpose**: User message display
- **Props**: content (text)
- **Features**: 
  - Right-aligned
  - Blue background
  - Simple text display

### 15. **FeedbackComponent**
- **Purpose**: User feedback collection (thumbs up/down + questionnaire)
- **Props**: 
  - messageId (for tracking)
  - onSubmit callback
- **Features**:
  - Thumbs up/down buttons (ChatGPT-style, no background)
  - Expandable questionnaire
  - Submit button
  - Auto-collapse after submission
  - Toggle to show/hide
- **Sub-components**:
  - ThumbsButtons
  - FeedbackQuestionnaire
  - FeedbackSubmit

### 16. **GuidanceActions**
- **Purpose**: Context-aware action buttons (Next Steps)
- **Props**: actions (array of {label, onClick})
- **Features**:
  - Blue background with left border
  - Dynamic button generation
  - Toggle to show/hide
- **Separate from**: FeedbackComponent (different styling)

## Input Components

### 17. **ChatInput**
- **Purpose**: Text input for chat messages
- **Props**: placeholder, onSend, value
- **Features**: Rounded input field

### 18. **ChatTools**
- **Purpose**: Standard tools (copy, email, save, more)
- **Props**: tools (array)
- **Features**:
  - Icon buttons
  - Dropdown menu for additional tools
  - Positioned next to chat input

### 19. **RecordIDInput**
- **Purpose**: Input for patient/claim/visit IDs
- **Props**: 
  - recordType (Patient ID | Claim ID | Visit ID | etc.)
  - value, onChange
- **Features**:
  - Dropdown for record type
  - Text input for ID
  - Single line layout

### 20. **WorkflowButtons**
- **Purpose**: Workflow-specific action buttons
- **Props**: buttons (array of {label, onClick})
- **Features**: 
  - Context-aware buttons
  - Positioned below Record ID input
  - Grey background

## Footer Components

### 21. **UserDetails**
- **Purpose**: Displays current user information
- **Props**: userName, userRole
- **Features**: Text display

### 22. **PreferencesPanel**
- **Purpose**: User preferences (LLM choice, Agent mode)
- **Props**: 
  - llmChoice, agentMode
  - onChange callbacks
- **Features**:
  - Collapsible
  - Compact display (collapsed)
  - Full controls (expanded)
  - Same line as user details when collapsed

## Composite Components

### 23. **ChatMessage** (Composite)
- **Composed of**: ThinkingBox + SystemMessage + FeedbackComponent + GuidanceActions
- **Purpose**: Complete system message with all features

### 24. **Header** (Composite)
- **Composed of**: ClientLogo + MobiusLogo + ContextDisplay + AlertButton + SettingsButton
- **Purpose**: Complete header bar

### 25. **ChatArea** (Container)
- **Purpose**: Container for chat messages
- **Features**: Scrollable, message list

## Utility Components

### 26. **CollapsiblePanel**
- **Purpose**: Generic collapsible container
- **Props**: 
  - header (text or component)
  - content (component)
  - isCollapsed, onToggle
- **Used by**: TasksPanel, ThinkingBox, PreferencesPanel

### 27. **DropdownMenu**
- **Purpose**: Generic dropdown menu
- **Props**: items (array), onSelect
- **Used by**: ChatTools, RecordIDInput

## Component Hierarchy

```
MockupContainer
├── Header
│   ├── ClientLogo
│   ├── MobiusLogo
│   ├── ContextDisplay
│   │   ├── StatusIndicator
│   │   └── ModeBadge
│   ├── AlertButton
│   └── SettingsButton
├── ContextSummary
│   └── QuickActionButton
├── TasksPanel
│   ├── TasksStatusIndicator
│   └── TaskItem[] (multiple)
├── ChatArea
│   ├── SystemMessage[]
│   │   ├── ThinkingBox
│   │   ├── MessageContent
│   │   ├── FeedbackComponent
│   │   └── GuidanceActions
│   └── UserMessage[]
├── ChatInput
│   └── ChatTools
├── RecordIDInput
├── WorkflowButtons
└── Footer
    ├── UserDetails
    └── PreferencesPanel
```

## Component Categories

### **Status & Indicators** (4)
- StatusIndicator
- TasksStatusIndicator
- MobiusLogo (status-aware)
- AlertButton (has alerts state)

### **Input & Forms** (4)
- ChatInput
- RecordIDInput
- FeedbackComponent (questionnaire)
- PreferencesPanel

### **Actions & Buttons** (5)
- QuickActionButton
- GuidanceActions
- WorkflowButtons
- ChatTools
- SettingsButton

### **Display & Content** (6)
- ClientLogo
- ContextDisplay
- ContextSummary
- SystemMessage
- UserMessage
- UserDetails

### **Interactive Panels** (3)
- TasksPanel
- ThinkingBox
- PreferencesPanel

### **Composite/Container** (3)
- ChatArea
- ChatMessage (composite)
- Header (composite)

## Total: 27 Reusable Components
