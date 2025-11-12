# Frontend Update Prompt for Summarise API Enhancement

## Context
The `/api/v2/summarise` endpoint has been enhanced to include `possibleQuestions` in the response. The frontend currently handles Server-Sent Events (SSE) for streaming the summary, and needs to be updated to handle the new `possibleQuestions` field.

## API Changes

### Previous Response Structure
The SSE stream previously sent:
1. **Chunk events** (during streaming):
   ```json
   {
     "chunk": "partial text chunk",
     "accumulated": "full accumulated summary so far"
   }
   ```

2. **Complete event** (after streaming):
   ```json
   {
     "type": "complete",
     "summary": "final complete summary"
   }
   ```

3. **Done event**: `"[DONE]"`

### New Response Structure
The SSE stream now sends:
1. **Chunk events** (during streaming) - **UNCHANGED**:
   ```json
   {
     "chunk": "partial text chunk",
     "accumulated": "full accumulated summary so far"
   }
   ```

2. **Complete event** (after streaming) - **UPDATED**:
   ```json
   {
     "type": "complete",
     "summary": "final complete summary",
     "possibleQuestions": [
       "Question 1 (most relevant)",
       "Question 2",
       "Question 3",
       "Question 4",
       "Question 5 (least relevant)"
     ]
   }
   ```

3. **Done event**: `"[DONE]"` - **UNCHANGED**

## Required Frontend Changes

### 1. Update State/Data Structure
- Add a state variable to store `possibleQuestions` (array of strings)
- Initialize it as an empty array `[]`

### 2. Update SSE Event Handler
In the event handler that processes the "complete" event:
- Extract the `possibleQuestions` field from the complete event data
- Store it in the state variable
- Handle the case where `possibleQuestions` might be missing or empty (for backward compatibility)

### 3. Update UI/Display
- Display the `possibleQuestions` array in the UI after the summary is complete
- Show them in a visually appealing way (e.g., as a list, cards, or clickable items)
- Maintain the order (most relevant first, as provided by the API)
- Consider making them clickable/interactive if your app supports asking questions
- Handle empty arrays gracefully (don't show the section if there are no questions)

### 4. Error Handling
- If `possibleQuestions` is missing from the response, handle gracefully (don't break the UI)
- If `possibleQuestions` is an empty array, optionally hide the questions section
- Ensure the summary display still works even if questions fail to load

## Implementation Guidelines

### Example Event Handler Update (Pseudocode)
```javascript
// In your SSE event handler
if (event.type === 'complete' || data.type === 'complete') {
  const { summary, possibleQuestions } = data;
  
  // Update summary state
  setSummary(summary);
  
  // Update possible questions state
  setPossibleQuestions(possibleQuestions || []); // Default to empty array if missing
}
```

### Example UI Component (Pseudocode)
```jsx
{possibleQuestions.length > 0 && (
  <div className="possible-questions-section">
    <h3>Possible Questions</h3>
    <ul>
      {possibleQuestions.map((question, index) => (
        <li key={index}>{question}</li>
      ))}
    </ul>
  </div>
)}
```

## Testing Checklist
- [ ] Verify summary still streams correctly
- [ ] Verify `possibleQuestions` are displayed after summary completes
- [ ] Verify questions are in the correct order (most relevant first)
- [ ] Test with empty `possibleQuestions` array
- [ ] Test with missing `possibleQuestions` field (backward compatibility)
- [ ] Verify UI doesn't break if questions fail to load
- [ ] Test with different languages (questions should match summary language)

## Notes
- The `possibleQuestions` array will always contain exactly 5 items (may include empty strings if generation fails)
- Questions are ordered by relevance/importance in decreasing order
- Questions are in the same language as the summary (or as specified by `languageCode`)
- The questions are generated after the summary streaming completes, so they appear in the final "complete" event only

