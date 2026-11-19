import { IsInt, IsOptional, IsString, Length, Max, Min } from 'class-validator';

/** GET /worlds query (ValidationPipe with implicit conversion: query values are strings). */
export class WorldsQuery {
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(10000)
  min: number = 1;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(10000)
  max: number = 10000;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  limit: number = 20;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(1000)
  page: number = 1;
}

/** PUT /world/:id body (no conversion: randomNumber must be a JSON integer). */
export class WorldUpdate {
  @IsInt()
  @Min(1)
  @Max(10000)
  randomNumber: number;
}

/** POST /form fields (urlencoded strings, converted by ValidationPipe). */
export class FormInput {
  @IsString()
  @Length(1, 64)
  name: string;

  @IsInt()
  @Min(1)
  @Max(10000)
  randomNumber: number;
}

export class LoginInput {
  @IsString()
  username: string;

  @IsString()
  password: string;
}
