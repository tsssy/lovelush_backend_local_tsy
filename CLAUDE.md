# Claude Code Development Standards

## Tech Stack

- **Framework**: FastAPI
- **Database**: MongoDB
- **Language**: Python 3.11+
- **Authentication**: JWT
- **Validation**: Pydantic

## Project Structure

```bash
app/
├── core/                    # Config, logging, dependencies
├── domain/                  # Business logic (models, services)
├── infrastructure/         # Database, security, external APIs
└── interfaces/            # API routes
```

## Core Standards

### Import Organization

- All imports at the top of file
- No inline imports (except circular import workarounds)
- Group: standard → third-party → local

### Business Logic Separation

- Routes are thin - delegate to services
- Services contain business logic and validation
- Use dependency injection for testability

### Error Handling

```python
# Use ResponseHelper for consistent responses
return ResponseHelper.success(data=result.model_dump(), msg="Success")
return ResponseHelper.error(msg="Error", code=400)

# Proper exception handling
try:
    result = await service.do_something()
    return ResponseHelper.success(data=result)
except NotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except Exception as e:
    logger.exception("Unexpected error: %s", str(e))
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Dependency Injection

- Use centralized container in `app/core/dependencies.py`
- Constructor injection for services
- Singleton repositories
- Never instantiate services/repos in routes

## Model Architecture

### Model Pattern Structure

All models follow: Base → Create/Update → Response → InDB

```python
# Entity pattern
class EntityBase(BaseModel):  # Shared fields
class EntityCreate(EntityBase):  # API input for creation
class EntityUpdate(BaseModel):  # API input for updates (all optional)
class EntityResponse(EntityBase):  # API output (excludes sensitive data)
class EntityInDB(EntityBase):  # DB storage (includes all fields)
Entity = EntityInDB  # Convenience alias
```

### Field Standards

- Use Field() with descriptions and validation
- PyObjectId for MongoDB _id fields
- String references for related entities
- Complete type hints

### PyObjectId Implementation

```python
class PyObjectId(ObjectId):
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
```

## Repository Standards

### Repository Pattern Structure

```python
# Interface definition
class EntityRepositoryInterface(BaseRepositoryInterface[Entity, EntityCreate, EntityUpdate]):
    async def domain_specific_method(self, param: str) -> Optional[Entity]:
        pass

# Implementation
class EntityRepository(BaseRepository, EntityRepositoryInterface):
    def __init__(self):
        super().__init__("collection_name", EntityModel)

    async def domain_specific_method(self, param: str) -> Optional[Entity]:
        try:
            doc = await self.collection.find_one({"field": param, "deleted_at": None})
            return Entity(**doc) if doc else None
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
```

### Key Rules

- Always exclude soft-deleted records (`deleted_at: None`)
- Comprehensive error handling with logging
- Use interface + implementation pattern
- Domain-specific methods in interface

## Service Layer Standards

### Service Pattern Structure

```python
class EntityService:
    def __init__(self, entity_repository: Optional[EntityRepository] = None):
        self.entity_repository = entity_repository or EntityRepository()

    async def create_entity(self, entity_data: EntityCreate) -> EntityResponse:
        # Business validation
        if await self.entity_repository.get_by_field(entity_data.field):
            raise ValidationError("Already exists")

        # Create and convert to response
        entity = await self.entity_repository.create(entity_data)
        return self._to_entity_response(entity)

    def _to_entity_response(self, entity: Entity) -> EntityResponse:
        return EntityResponse(**entity.model_dump())
```

### Service Key Rules

- Constructor injection with optional parameter
- Business validation before repository calls
- Convert domain models to response models
- Structured logging with context
- Proper exception handling

## Interface Layer Standards

### Route Structure

```python
@router.post("/", summary="Create entity")
async def create_entity(
    entity_data: EntityCreate,
    current_user: User = Depends(get_current_user),
    entity_service: EntityService = Depends(get_entity_service)
) -> Dict[str, Any]:
    """
    Create new entity with validation.

    Args:
        entity_data: Entity creation data
        current_user: Authenticated user
        entity_service: Injected service

    Returns:
        ResponseHelper.created with entity data

    Raises:
        HTTPException(400): Validation error
        HTTPException(409): Conflict error
    """
    try:
        entity = await entity_service.create_entity(entity_data)
        return ResponseHelper.created(data=entity.model_dump())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
```

### Route Key Rules

- RESTful endpoints with clear summaries
- Comprehensive docstrings
- Dependency injection for services and auth
- ResponseHelper for consistent responses
- Proper HTTPException handling

## Additional Standards

### Logging

- Use `get_logger(__name__)` with structured context
- Never use `print()` statements
- Include relevant data in `extra` parameter

### Type Hints & Documentation

- Complete type annotations on all functions
- Docstrings for classes and public methods
- Explain business logic, not obvious code

### Security & Performance

- Validate all input with Pydantic models
- Use authentication dependencies where required
- Proper async/await usage
- Database indexes for frequently queried fields

## Quality Checklist

- [ ] All imports at top of file
- [ ] Business logic in services, not routes
- [ ] ResponseHelper for consistent responses
- [ ] Type hints and docstrings
- [ ] Dependency injection used properly
- [ ] Repository methods exclude soft-deleted records
- [ ] Proper authentication and error handling

## Key Reminders

- **NEVER** create files unless absolutely necessary
- **ALWAYS** prefer editing existing files over creating new ones
- Use centralized dependency container for all services
- All database queries must exclude soft-deleted records (`deleted_at: None`)
