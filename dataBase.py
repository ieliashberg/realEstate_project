# create a python class for every table
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    "postgresql://localhost:5432/realEstate",
    echo=False,   # set True if you want to see the raw SQL
)

# session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# reflect only the tables you care about (or omit `only` to reflect all)
metadata = MetaData()
metadata.reflect(bind=engine)

# automap Base
Base = automap_base(metadata=metadata)
Base.prepare()   # actually generates the ORM classes


# assign Python names to the generated classes
School = Base.classes.school
Property_School_Join = Base.classes.property_school
Property = Base.classes.property
Price_History = Base.classes.price_history
Status_History = Base.classes.status_history
Listing = Base.classes.listing
Property_Change = Base.classes.property_change
Transaction = Base.classes.transaction
Zip_To_Url = Base.classes.zip_to_url

