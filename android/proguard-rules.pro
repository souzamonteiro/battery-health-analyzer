proguard-rules.pro

# AndroidX
-keep class androidx.** { *; }
-keep interface androidx.** { *; }

# Kotlin
-keep class kotlin.** { *; }
-keep interface kotlin.** { *; }

# Room
-keep class androidx.room.** { *; }
-keep interface androidx.room.** { *; }
-keepnames class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-keepclassmembers class * extends androidx.room.RoomDatabase {
  public abstract *Dao *();
}

# Compose
-keep class androidx.compose.** { *; }

# Keep all classes with annotations
-keepclasseswithmembers class * {
    @androidx.room.* <methods>;
}
