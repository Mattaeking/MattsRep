import arcpy
import os

# Define the input parameters
input_csv = arcpy.GetParameterAsText(0)  # Path to the input CSV file
output_gdb = arcpy.GetParameterAsText(1) # Path to the default geodatabase
output_fc = arcpy.GetParameterAsText(2)  # Output feature class name
dem_path = arcpy.GetParameterAsText(3)   # Path to the local DEM TIFF file
clipped_dem = arcpy.GetParameterAsText(4) # Output path for the clipped DEM

# Define the spatial reference for WGS 1984
wgs84 = arcpy.SpatialReference(4326)

# Define the spatial reference for NAD83
nad83 = arcpy.SpatialReference(4269)

# Define the spatial reference for Alberta 3TM 114
alberta_3tm = arcpy.SpatialReference(3776)

# Create a temporary table from the CSV
temp_table = "in_memory\\temp_table"
arcpy.TableToTable_conversion(input_csv, "in_memory", "temp_table")

# Define the X and Y fields (assuming 'Longitude' and 'Latitude' are the field names in your CSV)
x_field = "Longitude"
y_field = "Latitude"

# Check if the required fields exist in the CSV
field_names = [field.name for field in arcpy.ListFields(temp_table)]
for field in [x_field, y_field]:
    if field not in field_names:
        arcpy.AddError(f"CSV must contain fields '{x_field}' and '{y_field}'")
        raise ValueError(f"CSV must contain fields '{x_field}' and '{y_field}'")

# Create the point feature class in WGS 1984
temp_fc_wgs84 = "in_memory\\temp_fc_wgs84"
arcpy.management.XYTableToPoint(temp_table, temp_fc_wgs84, x_field, y_field, "", wgs84)

# Verify if the DEM file exists and is a valid raster
if not arcpy.Exists(dem_path):
    arcpy.AddError(f"DEM file at '{dem_path}' does not exist.")
    raise ValueError(f"DEM file at '{dem_path}' does not exist.")
if arcpy.Describe(dem_path).dataType != 'RasterDataset':
    arcpy.AddError(f"The file at '{dem_path}' is not a valid raster dataset.")
    raise ValueError(f"The file at '{dem_path}' is not a valid raster dataset.")

# Get the spatial reference of the DEM raster
dem_sr = arcpy.Describe(dem_path).spatialReference

# Project the point feature class from WGS 1984 to DEM raster's spatial reference
output_fc_path = os.path.join(output_gdb, output_fc)
arcpy.management.Project(temp_fc_wgs84, output_fc_path, dem_sr)

# Determine the extent of the points
extent = arcpy.Describe(output_fc_path).extent
xmin, ymin, xmax, ymax = extent.XMin, extent.YMin, extent.XMax, extent.YMax

# Buffer the extent slightly to ensure overlap
buffer = 200000  # Increased buffer size
xmin -= buffer
ymin -= buffer
xmax += buffer
ymax += buffer

# Get the extent of the DEM raster
dem_extent = arcpy.Describe(dem_path).extent
arcpy.AddMessage(f"Points extent: xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}")
arcpy.AddMessage(f"DEM extent: xmin={dem_extent.XMin}, ymin={dem_extent.YMin}, xmax={dem_extent.XMax}, ymax={dem_extent.YMax}")

# Check if the point extent overlaps the DEM extent
if xmin > dem_extent.XMax or xmax < dem_extent.XMin or ymin > dem_extent.YMax or ymax < dem_extent.YMin:
    arcpy.AddError("The extent of the points does not overlap with the extent of the DEM raster.")
    raise ValueError("The extent of the points does not overlap with the extent of the DEM raster.")

# Clip the DEM to the extent of the points and log the operation
try:
    arcpy.management.Clip(dem_path, f"{xmin} {ymin} {xmax} {ymax}", clipped_dem, "", "", "ClippingGeometry", "MAINTAIN_EXTENT")
    arcpy.AddMessage(f"DEM clipped successfully to the extent of the points and saved as '{clipped_dem}'")
except Exception as e:
    arcpy.AddError(f"Failed to clip DEM: {str(e)}")
    raise

# Clean up in-memory table and feature classes
arcpy.Delete_management(temp_table)
arcpy.Delete_management(temp_fc_wgs84)

# Set the output parameters
arcpy.SetParameterAsText(2, output_fc_path)
arcpy.SetParameterAsText(4, clipped_dem)

# Print messages
arcpy.AddMessage(f"Point feature class '{output_fc}' created in '{output_gdb}' with spatial reference matching DEM raster")
