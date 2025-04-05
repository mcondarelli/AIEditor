# AIEditorServer API Specification

## Base URL
`http://<host>:<port>/api/v1`

## Endpoints
### Scene Operations
`PUT /scenes/{id}`
```json
{
  "content": "scene text",
  "metadata": {
    "chapter": 1,
    "revision": "2024-06-01"
  }
}
```

### Analysis Requests
`GET /analyze/scene/{id}`
```json
{
  "similar_scenes": ["id1", "id2"],
  "theme_consistency": 0.85
}
```

## Error Codes
| Code | Meaning |
|------|---------|
| 423  | LLM not loaded |
| 429  | Rate limited |
```
